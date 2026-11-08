"""Charges API with server-owned operation ids (no client idempotency key).

Flow:
  POST /charges              -> create_charge: stores a `created` intent, moves no money.
  POST /charges/{id}/confirm -> confirm_charge: the only money-moving call. The Stripe
                                idempotency key is derived from the intent id, so any retry
                                of the same URL (timeout, double-click) is the same operation.

States: created -> pending -> succeeded | failed. Transitions are guarded in SQL.
A timeout leaves the intent `pending` (unknown outcome); reconcile_pending() resolves it.
"""
import random
import sqlite3
import time
import uuid

import stripe

RETRYABLE = (stripe.error.APIConnectionError, stripe.error.RateLimitError, stripe.error.APIError)


class RetryPolicy:
    max_attempts = 3
    max_total_seconds = 10.0
    base_delay = 0.2


POLICY = RetryPolicy()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS charges (
    id TEXT PRIMARY KEY,              -- server-generated operation id
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,             -- created | pending | succeeded | failed
    processor_ref TEXT,
    processor_status TEXT,
    created_at REAL NOT NULL
)"""


def get_db(path="charges.db"):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute(_SCHEMA)
    return db


def _view(row):
    return {"id": row["id"], "status": row["status"], "processor_status": row["processor_status"]}


def create_charge(request, db):
    amount, currency = request.json["amount"], request.json["currency"]
    if not isinstance(amount, int) or amount <= 0:
        return {"error": "invalid amount"}, 400
    charge_id = f"chg_{uuid.uuid4().hex}"
    db.execute("INSERT INTO charges (id, amount, currency, status, created_at) VALUES (?,?,?,?,?)",
               (charge_id, amount, currency, "created", time.time()))
    return {"id": charge_id, "status": "created"}, 201


def _call_stripe(row):
    """Single place that calls the processor. Key is derived from the intent id (rule 4)."""
    deadline = time.monotonic() + POLICY.max_total_seconds
    for attempt in range(1, POLICY.max_attempts + 1):
        try:
            return stripe.PaymentIntent.create(
                amount=row["amount"], currency=row["currency"],
                metadata={"charge_id": row["id"]},
                idempotency_key=f"charge-{row['id']}",
            )
        except RETRYABLE:
            delay = POLICY.base_delay * 2 ** (attempt - 1) * random.uniform(0.5, 1.5)
            if attempt == POLICY.max_attempts or time.monotonic() + delay > deadline:
                raise
            time.sleep(delay)


def confirm_charge(charge_id, db):
    row = db.execute("SELECT * FROM charges WHERE id=?", (charge_id,)).fetchone()
    if row is None:
        return {"error": "not found"}, 404
    if row["status"] in ("succeeded", "failed"):
        return _view(row), 200  # stored response; no second call

    # Guarded transition created -> pending. A retry of a `pending` intent is allowed
    # because the outbound key is identical, so the processor replays the same result.
    db.execute("UPDATE charges SET status='pending' WHERE id=? AND status='created'", (charge_id,))
    row = db.execute("SELECT * FROM charges WHERE id=?", (charge_id,)).fetchone()

    try:
        intent = _call_stripe(row)
    except stripe.error.InvalidRequestError as e:  # confirmed rejection (4xx): not retried
        db.execute("UPDATE charges SET status='failed' WHERE id=? AND status='pending'", (charge_id,))
        return {"id": charge_id, "status": "failed", "error": str(e)}, 400
    except stripe.error.CardError:
        db.execute("UPDATE charges SET status='failed' WHERE id=? AND status='pending'", (charge_id,))
        return {"id": charge_id, "status": "failed"}, 402
    except RETRYABLE:
        # Unknown outcome, NOT a failure. Stay pending; client retries same URL or reconciler resolves.
        return {"id": charge_id, "status": "pending"}, 202

    db.execute(
        "UPDATE charges SET status='succeeded', processor_ref=?, processor_status=? "
        "WHERE id=? AND status='pending'", (intent.id, intent.status, charge_id))
    row = db.execute("SELECT * FROM charges WHERE id=?", (charge_id,)).fetchone()
    return _view(row), 200


def reconcile_pending(db, older_than=60):
    """Resolve pending intents by asking the processor, using our reference."""
    cutoff = time.time() - older_than
    for row in db.execute("SELECT * FROM charges WHERE status='pending' AND created_at<?", (cutoff,)).fetchall():
        found = stripe.PaymentIntent.search(query=f"metadata['charge_id']:'{row['id']}'").data
        if found:
            db.execute("UPDATE charges SET status='succeeded', processor_ref=?, processor_status=? "
                       "WHERE id=? AND status='pending'", (found[0].id, found[0].status, row["id"]))
        else:
            confirm_charge(row["id"], db)  # same derived key: safe to re-drive
