"""POST /charges, idempotent.

Flow (see idempotent-payments rules 1-6, 9):
  1. Caller supplies an Idempotency-Key header (required).
  2. First writer wins: INSERT into a table with a UNIQUE (tenant, operation, key) index,
     state 'pending', before any processor call.
  3. The processor key is derived from our operation id, so every retry presents the same key.
  4. A timeout / exhausted retryable error is an UNKNOWN outcome: the row becomes 'unknown',
     never 'failed'. A retry with the same key (or the reconciler) re-drives it with the same
     processor key, so the processor returns the original charge instead of creating another.
  5. Only a confirmed processor rejection (4xx) makes the row 'failed'.
"""
import hashlib
import json
import random
import sqlite3
import threading
import time
import uuid

import stripe

OPERATION = "create_charge"


# --------------------------------------------------------------------------- store
class IdempotencyStore:
    def __init__(self, path=":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS charge_requests (
                op_id TEXT PRIMARY KEY,
                tenant TEXT NOT NULL,
                operation TEXT NOT NULL,
                idem_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                request TEXT NOT NULL,
                state TEXT NOT NULL,            -- pending | unknown | succeeded | failed
                http_status INTEGER,
                response TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_charge_requests_key
                ON charge_requests (tenant, operation, idem_key);
            """
        )

    def _run(self, sql, args=()):
        with self._lock:
            cur = self._db.execute(sql, args)
            return cur.rowcount, cur.fetchall()

    def begin(self, tenant, key, fingerprint, request_body):
        """Insert-first. Returns (row, created). Exactly one caller gets created=True."""
        op_id, now = str(uuid.uuid4()), time.time()
        n, _ = self._run(
            "INSERT OR IGNORE INTO charge_requests (op_id,tenant,operation,idem_key,fingerprint,"
            "request,state,created_at,updated_at) VALUES (?,?,?,?,?,?,'pending',?,?)",
            (op_id, tenant, OPERATION, key, fingerprint, json.dumps(request_body), now, now),
        )
        return self.get(tenant, key), n == 1

    def get(self, tenant, key):
        _, rows = self._run(
            "SELECT op_id,fingerprint,state,http_status,response FROM charge_requests "
            "WHERE tenant=? AND operation=? AND idem_key=?", (tenant, OPERATION, key))
        return self._row(rows[0]) if rows else None

    @staticmethod
    def _row(r):
        return {"op_id": r[0], "fingerprint": r[1], "state": r[2], "http_status": r[3],
                "response": json.loads(r[4]) if r[4] else None}

    def claim_unknown(self, op_id):
        """Guarded transition unknown -> pending; only one re-driver wins."""
        n, _ = self._run("UPDATE charge_requests SET state='pending',updated_at=? "
                         "WHERE op_id=? AND state='unknown'", (time.time(), op_id))
        return n == 1

    def finish(self, op_id, state, http_status=None, response=None):
        self._run("UPDATE charge_requests SET state=?,http_status=?,response=?,updated_at=? "
                  "WHERE op_id=? AND state IN ('pending','unknown')",
                  (state, http_status, json.dumps(response) if response is not None else None,
                   time.time(), op_id))

    def mark_unknown(self, op_id):
        self._run("UPDATE charge_requests SET state='unknown',updated_at=? "
                  "WHERE op_id=? AND state='pending'", (time.time(), op_id))

    def stale(self, older_than_s):
        _, rows = self._run(
            "SELECT op_id,fingerprint,state,http_status,response,request FROM "
            "charge_requests WHERE state IN ('pending','unknown') AND updated_at<?",
            (time.time() - older_than_s,))
        out = []
        for r in rows:
            d = self._row(r[:5])
            d["request"] = json.loads(r[5])
            out.append(d)
        return out


# --------------------------------------------------------------------------- processor
class RetryPolicy:
    max_attempts = 3
    max_total_s = 10.0
    base_delay_s = 0.2

    def __init__(self, max_attempts=3, max_total_s=10.0, base_delay_s=0.2, sleep=time.sleep):
        self.max_attempts, self.max_total_s = max_attempts, max_total_s
        self.base_delay_s, self.sleep = base_delay_s, sleep

    @staticmethod
    def retryable(exc):
        status = getattr(exc, "http_status", None)
        if status is None:          # network error / timeout: outcome unknown
            return True
        return status >= 500 or status == 429   # never 4xx validation errors or declines


class OutcomeUnknown(Exception):
    pass


class ProcessorRejected(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


class StripeProcessor:
    """The only place that calls Stripe. The key is derived from our operation id."""

    def __init__(self, policy=None):
        self.policy = policy or RetryPolicy()

    def create_charge(self, op_id, amount, currency):
        p, start = self.policy, time.monotonic()
        for attempt in range(1, p.max_attempts + 1):
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount, currency=currency,
                    metadata={"operation_id": op_id},
                    idempotency_key=f"charge:{op_id}",      # same on every attempt
                )
                return {"id": intent.id, "status": intent.status}
            except Exception as exc:  # noqa: BLE001
                if not p.retryable(exc):
                    raise ProcessorRejected(getattr(exc, "http_status", 400), str(exc)) from exc
                delay = p.base_delay_s * 2 ** (attempt - 1) * (0.5 + random.random() / 2)
                if attempt == p.max_attempts or time.monotonic() - start + delay > p.max_total_s:
                    raise OutcomeUnknown(str(exc)) from exc
                p.sleep(delay)


# --------------------------------------------------------------------------- endpoint
def fingerprint(body):
    canon = json.dumps({"amount": body["amount"], "currency": str(body["currency"]).lower()},
                       sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def _drive(store, processor, row, body):
    """Call the processor for a row we own and record the outcome."""
    try:
        resp = processor.create_charge(row["op_id"], body["amount"], body["currency"])
    except ProcessorRejected as e:
        out = {"error": "charge_rejected", "message": e.message}
        store.finish(row["op_id"], "failed", e.status, out)
        return out, e.status
    except OutcomeUnknown:
        store.mark_unknown(row["op_id"])
        return {"error": "outcome_unknown",
                "message": "Charge outcome unknown; retry with the same Idempotency-Key."}, 504
    store.finish(row["op_id"], "succeeded", 200, resp)
    return resp, 200


def create_charge(request, store, processor=None):
    """Returns (body, http_status)."""
    processor = processor or StripeProcessor()
    key = request.headers.get("Idempotency-Key")
    if not key or len(key) > 255:
        return {"error": "Idempotency-Key header required (max 255 chars)"}, 400
    body = request.json or {}
    if not isinstance(body.get("amount"), int) or body["amount"] <= 0 or not body.get("currency"):
        return {"error": "amount (positive int, minor units) and currency required"}, 400
    tenant = request.headers.get("X-Tenant-Id", "default")

    fp = fingerprint(body)
    row, created = store.begin(tenant, key, fp,
                               {"amount": body["amount"], "currency": body["currency"]})
    if not created:
        if row["fingerprint"] != fp:
            return {"error": "Idempotency-Key reused with different parameters"}, 422
        if row["state"] in ("succeeded", "failed"):
            return row["response"], row["http_status"]
        if row["state"] == "pending" or not store.claim_unknown(row["op_id"]):
            return {"error": "request in progress"}, 409
    return _drive(store, processor, row, body)


def reconcile(store, processor, older_than_s=60):
    """Resolve stale pending/unknown rows by re-driving with the same processor key
    (the processor returns the original charge if it was created). Run periodically and
    alert on rows that stay unresolved."""
    resolved = 0
    for row in store.stale(older_than_s):
        if row["state"] == "unknown" and not store.claim_unknown(row["op_id"]):
            continue                      # someone else is re-driving it
        _, status = _drive(store, processor, row, row["request"])
        resolved += status != 504
    return resolved
