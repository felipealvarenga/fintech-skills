"""POST /charges with idempotency, persist-before-call, and timeout-as-unknown-outcome.

States: pending -> authorized -> captured, plus failed (confirmed processor rejection only).
A processor timeout leaves the charge `pending`; the client retries with the same
Idempotency-Key and the processor key (derived from the charge id) is identical, so no
double charge. `reconcile_pending` resolves leftovers by querying the processor.
"""
import hashlib
import json
import logging
import random
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass

import stripe

log = logging.getLogger("charges")

SCHEMA = """
CREATE TABLE IF NOT EXISTS charges (
  id TEXT PRIMARY KEY,
  tenant TEXT NOT NULL,
  operation TEXT NOT NULL,
  key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  processor_ref TEXT,
  response TEXT,
  created_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS charges_idem ON charges (tenant, operation, key);
CREATE TABLE IF NOT EXISTS outbox (
  event_id TEXT PRIMARY KEY,
  charge_id TEXT NOT NULL,
  type TEXT NOT NULL,
  payload TEXT NOT NULL,
  published INTEGER NOT NULL DEFAULT 0
);
"""

TERMINAL = {"authorized", "captured", "failed"}


class InvalidTransition(Exception):
    def __init__(self, current):
        super().__init__(f"invalid transition from {current}")
        self.current = current


class Store:
    """SQLite store; one lock serialises access to the shared connection."""

    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()

    def insert_pending(self, tenant, operation, key, fingerprint):
        """First writer wins via the unique index. Returns (row, created)."""
        cid = str(uuid.uuid4())
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO charges (id, tenant, operation, key, fingerprint, status, created_at)"
                " VALUES (?,?,?,?,?, 'pending', ?) ON CONFLICT DO NOTHING",
                (cid, tenant, operation, key, fingerprint, time.time()),
            )
            row = self.db.execute(
                "SELECT * FROM charges WHERE tenant=? AND operation=? AND key=?",
                (tenant, operation, key),
            ).fetchone()
        return row, cur.rowcount == 1

    def get(self, charge_id):
        with self.lock:
            return self.db.execute("SELECT * FROM charges WHERE id=?", (charge_id,)).fetchone()

    def transition(self, charge_id, allowed_from, to, processor_ref=None):
        """Guarded update + outbox event in one transaction."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute("SELECT * FROM charges WHERE id=?", (charge_id,)).fetchone()
                if row["status"] not in allowed_from:
                    self.db.execute("ROLLBACK")
                    raise InvalidTransition(row["status"])
                body = {"id": charge_id, "status": to}
                self.db.execute(
                    "UPDATE charges SET status=?, processor_ref=COALESCE(?, processor_ref),"
                    " response=? WHERE id=?",
                    (to, processor_ref, json.dumps(body), charge_id),
                )
                self.db.execute(
                    "INSERT INTO outbox (event_id, charge_id, type, payload) VALUES (?,?,?,?)",
                    (str(uuid.uuid4()), charge_id, f"charge.{to}", json.dumps(body)),
                )
                self.db.execute("COMMIT")
            except InvalidTransition:
                raise
            except Exception:
                self.db.execute("ROLLBACK")
                raise
        return body

    def pending_older_than(self, seconds):
        with self.lock:
            return self.db.execute(
                "SELECT * FROM charges WHERE status='pending' AND created_at < ?",
                (time.time() - seconds,),
            ).fetchall()


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    max_total_seconds: float = 10.0
    base_delay: float = 0.2
    retryable: tuple = (stripe.error.APIConnectionError, stripe.error.APIError,
                        stripe.error.RateLimitError)


DEFAULT_POLICY = RetryPolicy()


def call_with_retry(fn, policy=DEFAULT_POLICY, sleep=time.sleep):
    """Retry only network errors, 5xx and 429. Validation errors and declines raise at once."""
    start = time.monotonic()
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except policy.retryable:
            elapsed = time.monotonic() - start
            if attempt == policy.max_attempts or elapsed >= policy.max_total_seconds:
                raise
            sleep(policy.base_delay * 2 ** (attempt - 1) * (0.5 + random.random()))


class Processor:
    """Only way to reach Stripe. Outbound key is derived from our charge id (never random)."""

    def __init__(self, policy=DEFAULT_POLICY, sleep=time.sleep):
        self.policy, self.sleep = policy, sleep

    def create(self, charge_id, amount, currency):
        return call_with_retry(
            lambda: stripe.PaymentIntent.create(
                amount=amount, currency=currency,
                metadata={"charge_id": charge_id},
                idempotency_key=f"charge:{charge_id}",
            ),
            self.policy, self.sleep,
        )

    def capture(self, charge_id, processor_ref):
        return call_with_retry(
            lambda: stripe.PaymentIntent.capture(
                processor_ref, idempotency_key=f"capture:{charge_id}"),
            self.policy, self.sleep,
        )

    def find(self, charge_id):
        """Look up by our reference; returns the intent or None."""
        res = stripe.PaymentIntent.search(query=f"metadata['charge_id']:'{charge_id}'")
        return res.data[0] if res.data else None


def _fingerprint(payload):
    canon = json.dumps({"amount": payload["amount"], "currency": payload["currency"]},
                       sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def _apply_intent(store, charge_id, intent):
    """Record a processor-confirmed outcome. Unknown statuses stay pending."""
    to = {"succeeded": "captured", "requires_capture": "authorized"}.get(intent.status)
    if to is None:
        return {"id": charge_id, "status": "pending"}
    try:
        return store.transition(charge_id, {"pending"}, to, processor_ref=intent.id)
    except InvalidTransition:
        return json.loads(store.get(charge_id)["response"])


def create_charge(request, store, processor):
    key = request.headers.get("Idempotency-Key")
    if not key:
        return {"error": "Idempotency-Key header required"}, 400
    tenant = request.headers.get("X-Tenant-Id", "default")
    fp = _fingerprint(request.json)

    row, _created = store.insert_pending(tenant, "create_charge", key, fp)
    if row["fingerprint"] != fp:
        return {"error": "Idempotency-Key reused with different parameters"}, 422
    if row["status"] in TERMINAL:
        return json.loads(row["response"]), 200

    charge_id = row["id"]
    # status is pending: either we just created it, or an earlier attempt timed out / is in
    # flight. Same charge id => same processor key => the processor dedupes.
    try:
        intent = processor.create(charge_id, request.json["amount"], request.json["currency"])
    except (stripe.error.CardError, stripe.error.InvalidRequestError) as e:
        # Confirmed rejection by the processor: the only path to `failed`.
        log.info("charge %s rejected: %s", charge_id, e)
        try:
            return store.transition(charge_id, {"pending"}, "failed"), 200
        except InvalidTransition:
            return json.loads(store.get(charge_id)["response"]), 200
    except (stripe.error.APIConnectionError, stripe.error.APIError,
            stripe.error.RateLimitError) as e:
        # Unknown outcome. Do NOT mark failed: the charge may exist at the processor.
        log.warning("charge %s outcome unknown (%s); left pending", charge_id, type(e).__name__)
        return {"id": charge_id, "status": "pending",
                "message": "Processing timed out. Retry with the same Idempotency-Key."}, 202

    body = _apply_intent(store, charge_id, intent)
    return body, 200


def capture_charge(store, processor, charge_id):
    row = store.get(charge_id)
    if row is None:
        return {"error": "not found"}, 404
    try:
        store.transition(charge_id, {"authorized"}, "captured")  # guard before the call
    except InvalidTransition as e:
        return {"error": "invalid state", "status": e.current}, 409
    processor.capture(charge_id, row["processor_ref"])
    return json.loads(store.get(charge_id)["response"]), 200


def reconcile_pending(store, processor, older_than_seconds=60):
    """Resolve stale pending charges from the processor's answer. Returns ids still unresolved
    (alert on these). Not found at the processor is NOT proof of failure, so they stay pending."""
    unresolved = []
    for row in store.pending_older_than(older_than_seconds):
        intent = processor.find(row["id"])
        if intent is None:
            unresolved.append(row["id"])
            continue
        if _apply_intent(store, row["id"], intent)["status"] == "pending":
            unresolved.append(row["id"])
    return unresolved
