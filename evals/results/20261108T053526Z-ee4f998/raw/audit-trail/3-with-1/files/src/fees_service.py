"""Fee schedule service.

Every fee change writes an append-only audit event in the same transaction
(audit-trail rules 1-6). If the event write fails, the fee change rolls back.
"""
import json
import uuid

REASON_CODES = {"pricing_review", "regulatory", "promo_start", "promo_end", "correction"}


def update_fee(db, fee_id: str, bps: int, *, actor_type: str, actor_id: str,
               reason_code: str, reason: str, request_id: str,
               on_behalf_of: str | None = None, approver_id: str | None = None):
    """Update a fee and record who/why. `db` must be a connection whose
    transaction() context commits or rolls back both statements together."""
    if reason_code not in REASON_CODES:
        raise ValueError(f"reason_code must be one of {sorted(REASON_CODES)}")
    if not reason or not reason.strip():
        raise ValueError("reason (free text or ticket reference) is required")

    with db.transaction():
        row = db.execute("SELECT bps FROM fees WHERE id = %s FOR UPDATE", (fee_id,)).fetchone()
        if row is None:
            raise KeyError(fee_id)
        before = row[0]

        db.execute("UPDATE fees SET bps = %s, updated_at = now() WHERE id = %s", (bps, fee_id))

        # Per-object gapless sequence; safe because the fee row is locked above.
        seq = db.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_events "
            "WHERE object_type = 'fee' AND object_id = %s", (fee_id,)
        ).fetchone()[0]

        db.execute(
            "INSERT INTO audit_events (event_id, object_type, object_id, sequence, action, "
            "actor_type, actor_id, on_behalf_of, approver_id, before, after, reason_code, "
            "reason, request_id, occurred_at, recorded_at, source) "
            "VALUES (%s,'fee',%s,%s,'fee.update',%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now(), 'fees_service')",
            (str(uuid.uuid4()), fee_id, seq, actor_type, actor_id, on_behalf_of, approver_id,
             json.dumps({"bps": before}), json.dumps({"bps": bps}),
             reason_code, reason, request_id),
        )
