"""Charges API with server-issued operation ids.

Flow (the client never invents a key):
  1. POST /charges            -> server validates, persists a `pending` intent with a
                                 server-generated operation id, returns {"operation_id": ...}.
  2. POST /charges/<id>/confirm -> server calls the processor with a key derived from the
                                 operation id. Retrying step 2 (timeout, double-click, redelivery)
                                 reuses the same key, so at most one charge exists.

Step 1 is safe to repeat: a lost response only leaves an unused pending intent.
"""
import hashlib
import sqlite3
import uuid

import stripe

_db = sqlite3.connect("charges.db", check_same_thread=False, isolation_level=None)
_db.execute(
    """CREATE TABLE IF NOT EXISTS charge_intents (
           operation_id TEXT PRIMARY KEY,           -- unique index: first writer wins
           amount INTEGER NOT NULL,
           currency TEXT NOT NULL,
           status TEXT NOT NULL,                    -- pending | succeeded | failed
           processor_ref TEXT,
           processor_status TEXT
       )"""
)


def _processor_key(operation_id: str) -> str:
    # Deterministic: every attempt for this operation presents the same key (rule 4).
    return "charge-" + hashlib.sha256(operation_id.encode()).hexdigest()


def create_charge(request):
    """Step 1: persist the intent before any processor call (rule 6)."""
    amount, currency = request.json["amount"], request.json["currency"]
    if not isinstance(amount, int) or amount <= 0:
        return {"error": "invalid amount"}, 400
    operation_id = str(uuid.uuid4())
    _db.execute(
        "INSERT INTO charge_intents (operation_id, amount, currency, status) "
        "VALUES (?, ?, ?, 'pending')",
        (operation_id, amount, currency),
    )
    return {"operation_id": operation_id, "status": "pending"}, 201


def confirm_charge(operation_id: str):
    """Step 2: idempotent. Same operation id -> same processor key -> one charge."""
    row = _db.execute(
        "SELECT amount, currency, status, processor_ref, processor_status "
        "FROM charge_intents WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    if row is None:
        return {"error": "unknown operation"}, 404
    amount, currency, status, ref, pstatus = row
    if status == "succeeded":  # stored response; no second call
        return {"id": ref, "status": pstatus}, 200
    if status == "failed":
        return {"error": "charge failed", "operation_id": operation_id}, 409

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount, currency=currency,
            idempotency_key=_processor_key(operation_id),
        )
    except (stripe.error.APIConnectionError, stripe.error.RateLimitError):
        # Timeout / unknown outcome (rule 5): stay pending, client retries confirm with the
        # same operation id. A reconciler should resolve stale pending rows.
        return {"status": "pending", "operation_id": operation_id}, 202
    except stripe.error.InvalidRequestError as exc:  # confirmed rejection: not retried
        _db.execute(
            "UPDATE charge_intents SET status='failed' WHERE operation_id=? AND status='pending'",
            (operation_id,),
        )
        return {"error": str(exc)}, 400

    _db.execute(
        "UPDATE charge_intents SET status='succeeded', processor_ref=?, processor_status=? "
        "WHERE operation_id=? AND status='pending'",
        (intent.id, intent.status, operation_id),
    )
    return {"id": intent.id, "status": intent.status}, 200
