"""POST /charges with idempotency and safe timeout handling.

A processor timeout is an UNKNOWN outcome, so the charge is left `pending`
(never `failed`). The client retries with the same Idempotency-Key, which
re-sends the same Stripe key, so Stripe returns the original result instead
of creating a second charge. Only a confirmed processor error marks `failed`.
"""
import hashlib
import json
import sqlite3
import stripe

OPERATION = "create_charge"

_db = sqlite3.connect("charges.db", check_same_thread=False, isolation_level=None)
_db.execute(
    """CREATE TABLE IF NOT EXISTS idempotency (
        tenant TEXT NOT NULL, operation TEXT NOT NULL, key TEXT NOT NULL,
        fingerprint TEXT NOT NULL, status TEXT NOT NULL, response TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (tenant, operation, key))"""
)


def _fingerprint(body):
    canon = json.dumps({"amount": body["amount"], "currency": body["currency"]}, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def _finish(tenant, key, status, response):
    # Guarded transition: only a pending row can be resolved.
    _db.execute(
        "UPDATE idempotency SET status=?, response=? "
        "WHERE tenant=? AND operation=? AND key=? AND status='pending'",
        (status, json.dumps(response), tenant, OPERATION, key),
    )


def create_charge(request):
    key = request.headers.get("Idempotency-Key")
    if not key:
        return {"error": "Idempotency-Key header required"}, 400
    tenant = request.headers.get("X-Tenant", "default")
    body = request.json
    fp = _fingerprint(body)

    # Persist before calling the processor; first writer wins (unique PK).
    _db.execute(
        "INSERT OR IGNORE INTO idempotency (tenant, operation, key, fingerprint, status) "
        "VALUES (?, ?, ?, ?, 'pending')",
        (tenant, OPERATION, key, fp),
    )
    stored_fp, status, response = _db.execute(
        "SELECT fingerprint, status, response FROM idempotency "
        "WHERE tenant=? AND operation=? AND key=?",
        (tenant, OPERATION, key),
    ).fetchone()

    if stored_fp != fp:
        return {"error": "Idempotency-Key reused with different parameters"}, 422
    if status != "pending":
        return json.loads(response), (200 if status == "succeeded" else 402)

    try:
        intent = stripe.PaymentIntent.create(
            amount=body["amount"], currency=body["currency"],
            # Deterministic: a retry after a timeout presents the same key.
            idempotency_key=f"{tenant}:{OPERATION}:{key}",
        )
    except (stripe.error.APIConnectionError, stripe.error.RateLimitError, stripe.error.APIError):
        # Includes timeouts. Outcome unknown: stay pending, do NOT mark failed.
        # Retrying with the same Idempotency-Key is safe; a reconciler should
        # resolve pending rows older than the SLA by querying Stripe.
        return {"status": "pending", "retry_with_same_idempotency_key": True}, 202
    except (stripe.error.CardError, stripe.error.InvalidRequestError) as e:
        # Confirmed rejection by the processor: safe to mark failed.
        result = {"status": "failed", "error": str(e)}
        _finish(tenant, key, "failed", result)
        return result, 402

    result = {"id": intent.id, "status": intent.status}
    _finish(tenant, key, "succeeded", result)
    return result, 200
