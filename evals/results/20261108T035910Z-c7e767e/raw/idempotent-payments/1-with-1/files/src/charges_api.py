"""POST /charges with idempotency.

Rules applied (see idempotent-payments skill):
- Caller supplies Idempotency-Key; server stores fingerprint + response (1, 2).
- Unique index on (tenant, operation, key) decides the first writer (3).
- Stripe key is derived from the persisted operation id, never random (4).
- A timeout is an unknown outcome: row stays 'unknown', retry reuses the same key (5).
- Intent is persisted as 'pending' before the processor call (6).
- Bounded retries on retryable errors only (9).
"""
import hashlib
import json
import logging
import random
import sqlite3
import time
import uuid

import stripe

log = logging.getLogger("charges")

OPERATION = "create_charge"
MAX_ATTEMPTS = 3
MAX_TOTAL_SECONDS = 10.0
BASE_BACKOFF = 0.2

_db = sqlite3.connect("charges.db", check_same_thread=False, isolation_level=None)
_db.execute(
    """CREATE TABLE IF NOT EXISTS idempotency (
        tenant TEXT NOT NULL, operation TEXT NOT NULL, key TEXT NOT NULL,
        op_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
        status TEXT NOT NULL,            -- pending | unknown | succeeded | failed
        http_status INTEGER, response TEXT,
        created_at REAL NOT NULL,
        PRIMARY KEY (tenant, operation, key))"""
)


def set_db(conn):
    """Test hook: swap the database connection."""
    global _db
    _db = conn


def _fingerprint(body):
    canon = json.dumps(
        {"amount": body.get("amount"), "currency": str(body.get("currency", "")).lower()},
        sort_keys=True,
    )
    return hashlib.sha256(canon.encode()).hexdigest()


def _is_retryable(exc):
    if isinstance(exc, (stripe.error.APIConnectionError, stripe.error.RateLimitError)):
        return True
    return isinstance(exc, stripe.error.APIError) and (getattr(exc, "http_status", 500) or 500) >= 500


def _call_processor(op_id, amount, currency):
    """Only place that calls Stripe. Same op_id -> same idempotency key on every attempt."""
    start = time.monotonic()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            log.info("charge attempt op=%s attempt=%d", op_id, attempt)
            return stripe.PaymentIntent.create(
                amount=amount, currency=currency,
                idempotency_key=f"charge:{op_id}",
                metadata={"op_id": op_id},
            )
        except Exception as exc:
            out_of_budget = (
                attempt == MAX_ATTEMPTS
                or time.monotonic() - start >= MAX_TOTAL_SECONDS
            )
            if not _is_retryable(exc) or out_of_budget:
                raise
            time.sleep(BASE_BACKOFF * 2 ** (attempt - 1) * (0.5 + random.random()))


def _finish(tenant, key, status, http_status=None, response=None):
    _db.execute(
        "UPDATE idempotency SET status=?, http_status=?, response=? "
        "WHERE tenant=? AND operation=? AND key=?",
        (status, http_status, json.dumps(response) if response is not None else None,
         tenant, OPERATION, key),
    )


def _execute(tenant, key, op_id, body):
    try:
        intent = _call_processor(op_id, body["amount"], body["currency"])
    except (stripe.error.CardError, stripe.error.InvalidRequestError) as exc:
        # Confirmed rejection from the processor: safe to record as failed.
        resp = {"error": str(exc)}
        code = 402 if isinstance(exc, stripe.error.CardError) else 400
        _finish(tenant, key, "failed", code, resp)
        return resp, code
    except Exception:
        # Unknown outcome (timeout, 5xx after retries, etc.). Do NOT mark failed.
        # A retry with the same Idempotency-Key re-drives with the same Stripe key;
        # a reconciler should also resolve rows stuck in 'unknown'/'pending'.
        log.exception("charge outcome unknown op=%s", op_id)
        _finish(tenant, key, "unknown")
        return {"error": "outcome unknown, retry with the same Idempotency-Key"}, 503
    resp = {"id": intent.id, "status": intent.status}
    _finish(tenant, key, "succeeded", 200, resp)
    return resp, 200


def create_charge(request):
    key = request.headers.get("Idempotency-Key")
    if not key:
        return {"error": "Idempotency-Key header required"}, 400
    body = request.json or {}
    if not isinstance(body.get("amount"), int) or body["amount"] <= 0 or not body.get("currency"):
        return {"error": "invalid amount or currency"}, 400
    tenant = request.headers.get("X-Tenant-Id", "default")
    fp = _fingerprint(body)

    # Persist intent before calling the processor; the unique key picks the winner.
    op_id = uuid.uuid4().hex
    cur = _db.execute(
        "INSERT INTO idempotency (tenant, operation, key, op_id, fingerprint, status, created_at) "
        "VALUES (?,?,?,?,?,'pending',?) ON CONFLICT DO NOTHING",
        (tenant, OPERATION, key, op_id, fp, time.time()),
    )
    if cur.rowcount == 1:
        return _execute(tenant, key, op_id, body)

    row = _db.execute(
        "SELECT op_id, fingerprint, status, http_status, response FROM idempotency "
        "WHERE tenant=? AND operation=? AND key=?", (tenant, OPERATION, key),
    ).fetchone()
    stored_op, stored_fp, status, http_status, response = row
    if stored_fp != fp:
        return {"error": "Idempotency-Key reused with different parameters"}, 422
    if status in ("succeeded", "failed"):
        return json.loads(response), http_status
    if status == "unknown":
        # Claim the re-drive atomically so only one retry runs; same op_id => same Stripe key.
        claimed = _db.execute(
            "UPDATE idempotency SET status='pending' WHERE tenant=? AND operation=? "
            "AND key=? AND status='unknown'", (tenant, OPERATION, key),
        ).rowcount
        if claimed == 1:
            return _execute(tenant, key, stored_op, body)
    return {"error": "request in progress"}, 409
