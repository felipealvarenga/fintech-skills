"""Admin endpoint: change a customer's transfer limit.

Every change writes an append-only audit event in the SAME transaction as the
update. If the event write fails, the limit change is rolled back.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

OBJECT_TYPE = "customer_transfer_limit"
ACTION = "transfer_limit.set"

# Fixed reason codes; free text / ticket reference is additional, not a substitute.
REASON_CODES = frozenset({
    "customer_request",
    "kyc_upgrade",
    "kyc_downgrade",
    "risk_review",
    "fraud_suspicion",
    "regulatory_requirement",
    "correction",
})

ACTOR_TYPES = frozenset({"user", "service", "agent", "system"})


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def set_transfer_limit(
    db,
    customer_id: str,
    new_limit_minor: int,
    *,
    actor_type: str,
    actor_id: str,
    reason_code: str,
    reason_text: str,
    request_id: str,
    on_behalf_of: str | None = None,
    authorization_ref: str | None = None,  # policy/run id for agents, ticket for humans
    idempotency_key: str | None = None,
    occurred_at: datetime | None = None,
    source: str = "admin_api",
):
    # Validate before touching the database: a rejected call writes nothing.
    if actor_type not in ACTOR_TYPES:
        raise ValueError("invalid actor_type")
    if not actor_id:
        raise ValueError("actor_id is required")
    if reason_code not in REASON_CODES:
        raise ValueError("reason_code must be one of the fixed reason codes")
    if actor_type in ("user", "agent") and not (reason_text or "").strip():
        raise ValueError("reason_text or ticket reference is required")
    if actor_type == "agent" and not (on_behalf_of and authorization_ref):
        raise ValueError("agent actions require on_behalf_of and authorization_ref")
    if not request_id:
        raise ValueError("request_id is required")
    if not isinstance(new_limit_minor, int) or isinstance(new_limit_minor, bool) or new_limit_minor < 0:
        raise ValueError("new_limit_minor must be a non-negative integer (minor units)")

    occurred_at = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)

    try:
        # Row lock serializes concurrent writers per customer, which makes the
        # per-object sequence gapless and the `before` value trustworthy.
        row = db.execute(
            "SELECT transfer_limit FROM customers WHERE id = %s FOR UPDATE", (customer_id,)
        ).fetchone()
        if row is None:
            raise LookupError("customer not found")
        before_limit = row[0]

        last = db.execute(
            "SELECT sequence, event_hash FROM audit_events "
            "WHERE object_type = %s AND object_id = %s ORDER BY sequence DESC LIMIT 1",
            (OBJECT_TYPE, customer_id),
        ).fetchone()
        sequence = (last[0] + 1) if last else 1
        prev_hash = last[1] if last else None

        event_id = str(uuid.uuid4())
        before = {"transfer_limit_minor": before_limit}
        after = {"transfer_limit_minor": new_limit_minor}

        body = {
            "event_id": event_id,
            "object_type": OBJECT_TYPE,
            "object_id": customer_id,
            "sequence": sequence,
            "action": ACTION,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "on_behalf_of": on_behalf_of,
            "authorization_ref": authorization_ref,
            "before": before,
            "after": after,
            "reason_code": reason_code,
            "reason_text": reason_text,
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "occurred_at": occurred_at.isoformat(),
            "source": source,
            "prev_hash": prev_hash,
        }
        event_hash = hashlib.sha256(_canonical(body).encode()).hexdigest()

        db.execute(
            "UPDATE customers SET transfer_limit = %s WHERE id = %s",
            (new_limit_minor, customer_id),
        )
        # recorded_at comes from the database clock (column default now() at UTC).
        db.execute(
            "INSERT INTO audit_events (event_id, object_type, object_id, sequence, action, "
            "actor_type, actor_id, on_behalf_of, authorization_ref, before, after, "
            "reason_code, reason_text, request_id, idempotency_key, occurred_at, source, "
            "prev_hash, event_hash) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                event_id, OBJECT_TYPE, customer_id, sequence, ACTION,
                actor_type, actor_id, on_behalf_of, authorization_ref,
                _canonical(before), _canonical(after),
                reason_code, reason_text, request_id, idempotency_key, occurred_at, source,
                prev_hash, event_hash,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"event_id": event_id, "sequence": sequence}
