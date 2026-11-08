"""Fee schedule service."""
import json
import uuid

REASON_CODES = {"PRICING_CHANGE", "CORRECTION", "PROMOTION", "REGULATORY", "OTHER"}
ACTOR_TYPES = {"user", "service", "agent", "system"}


def update_fee(
    db,
    fee_id: str,
    bps: int,
    *,
    actor_type: str,
    actor_id: str,
    reason_code: str,
    request_id: str,
    reason_text: str | None = None,
    on_behalf_of: str | None = None,
):
    """Update a fee and record an audit event.

    The caller owns the transaction: the fee update and the audit event are
    committed or rolled back together. Do not autocommit between them.
    """
    if actor_type not in ACTOR_TYPES:
        raise ValueError(f"invalid actor_type: {actor_type}")
    if reason_code not in REASON_CODES:
        raise ValueError(f"invalid reason_code: {reason_code}")
    if actor_type in ("user", "agent") and not reason_text:
        raise ValueError("reason_text is required for human or agent actions")

    # Lock the row so before-values and the per-object sequence are consistent.
    row = db.execute("SELECT bps FROM fees WHERE id = %s FOR UPDATE", (fee_id,)).fetchone()
    if row is None:
        raise LookupError(f"fee not found: {fee_id}")
    before_bps = row[0]

    db.execute(
        "UPDATE fees SET bps = %s, updated_by = %s, updated_at = now() WHERE id = %s",
        (bps, actor_id, fee_id),
    )

    db.execute(
        """
        INSERT INTO audit_events
          (event_id, object_type, object_id, sequence, action,
           actor_type, actor_id, on_behalf_of, before, after,
           reason_code, reason_text, request_id, occurred_at, recorded_at, source)
        VALUES
          (%s, 'fee', %s,
           (SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_events
             WHERE object_type = 'fee' AND object_id = %s),
           'fee.update', %s, %s, %s, %s, %s, %s, %s, %s, now(), now(), 'fees_service')
        """,
        (
            str(uuid.uuid4()), fee_id, fee_id,
            actor_type, actor_id, on_behalf_of,
            json.dumps({"bps": before_bps}), json.dumps({"bps": bps}),
            reason_code, reason_text, request_id,
        ),
    )
