"""Admin endpoint: change a customer's transfer limit.

Every change writes an append-only audit event in the same transaction as the
UPDATE. If the event write fails, the limit change is rolled back.
"""
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

REASON_CODES = frozenset({
    "customer_request",
    "risk_review",
    "kyc_upgrade",
    "fraud_suspicion",
    "compliance_order",
    "correction",
})
ACTOR_TYPES = frozenset({"user", "service", "agent", "system"})


class AuditError(ValueError):
    pass


@dataclass(frozen=True)
class Actor:
    actor_type: str
    actor_id: str
    on_behalf_of: Optional[str] = None  # required context for agents / support acting for a customer


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def set_transfer_limit(
    db,
    customer_id: str,
    new_limit_minor: int,
    *,
    actor: Actor,
    reason_code: str,
    reason_text: str = "",
    request_id: str,
    idempotency_key: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
    source: str = "admin_api",
):
    if not isinstance(new_limit_minor, int) or isinstance(new_limit_minor, bool) or new_limit_minor < 0:
        raise ValueError("new_limit_minor must be a non-negative integer (minor units)")
    if reason_code not in REASON_CODES:
        raise AuditError(f"reason_code must be one of {sorted(REASON_CODES)}")
    if actor.actor_type not in ACTOR_TYPES or not actor.actor_id:
        raise AuditError("actor requires a valid actor_type and actor_id")
    if actor.actor_type == "agent" and not actor.on_behalf_of:
        raise AuditError("agent actions require on_behalf_of")
    if actor.actor_type in ("user", "agent") and not (reason_text or "").strip():
        raise AuditError("human/agent actions require reason text or a ticket reference")
    if not request_id:
        raise AuditError("request_id is required")

    occurred_at = occurred_at or datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        raise AuditError("occurred_at must be timezone-aware (UTC)")
    occurred_at = occurred_at.astimezone(timezone.utc)

    try:
        # Lock the customer row: serialises writers so sequence is gapless per object.
        db.execute(
            "SELECT transfer_limit FROM customers WHERE id = %s FOR UPDATE", (customer_id,)
        )
        row = db.fetchone()
        if row is None:
            raise LookupError(f"customer {customer_id} not found")
        old_limit = row[0]

        db.execute(
            "SELECT sequence, event_hash FROM audit_events "
            "WHERE object_type = 'customer_transfer_limit' AND object_id = %s "
            "ORDER BY sequence DESC LIMIT 1",
            (customer_id,),
        )
        last = db.fetchone()
        sequence = (last[0] + 1) if last else 1
        prev_hash = last[1] if last else ""

        before = {"transfer_limit_minor": old_limit}
        after = {"transfer_limit_minor": new_limit_minor}
        event_id = str(uuid.uuid4())
        event_hash = hashlib.sha256(
            (prev_hash + _canonical({
                "event_id": event_id,
                "object_id": customer_id,
                "sequence": sequence,
                "action": "transfer_limit.set",
                "actor_type": actor.actor_type,
                "actor_id": actor.actor_id,
                "on_behalf_of": actor.on_behalf_of,
                "before": before,
                "after": after,
                "reason_code": reason_code,
                "reason_text": reason_text,
                "request_id": request_id,
                "occurred_at": occurred_at.isoformat(),
            })).encode()
        ).hexdigest()

        db.execute(
            "UPDATE customers SET transfer_limit = %s WHERE id = %s",
            (new_limit_minor, customer_id),
        )
        db.execute(
            "INSERT INTO audit_events (event_id, object_type, object_id, sequence, action, "
            "actor_type, actor_id, on_behalf_of, before, after, reason_code, reason_text, "
            "request_id, idempotency_key, occurred_at, recorded_at, source, prev_hash, event_hash) "
            "VALUES (%s, 'customer_transfer_limit', %s, %s, 'transfer_limit.set', %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s)",
            (
                event_id, customer_id, sequence, actor.actor_type, actor.actor_id,
                actor.on_behalf_of, _canonical(before), _canonical(after), reason_code,
                reason_text, request_id, idempotency_key, occurred_at, source,
                prev_hash, event_hash,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return event_id
