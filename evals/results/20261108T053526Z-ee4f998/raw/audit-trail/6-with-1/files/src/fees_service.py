"""Fee schedule service."""

REASON_CODES = {"pricing_change", "correction", "promotion", "regulatory", "other"}


def update_fee(db, fee_id: str, bps: int, *, actor_id: str, actor_type: str = "user",
               reason_code: str, reason: str = "", request_id: str,
               on_behalf_of: str | None = None):
    """Update a fee and record who/when/why in the same transaction.

    updated_by/updated_at on `fees` only show the latest change; the full history
    lives in `fee_audit_events` (append-only, one event per change).
    """
    if reason_code not in REASON_CODES:
        raise ValueError(f"invalid reason_code: {reason_code}")
    if not actor_id:
        raise ValueError("actor_id is required")

    with db.transaction():  # event write failure rolls back the mutation
        row = db.execute("SELECT bps FROM fees WHERE id = %s FOR UPDATE", (fee_id,)).fetchone()
        if row is None:
            raise LookupError(f"fee not found: {fee_id}")
        before = row[0]

        db.execute(
            "UPDATE fees SET bps = %s, updated_by = %s, updated_at = now() WHERE id = %s",
            (bps, actor_id, fee_id),
        )
        # Row lock on the fee above serializes writers, so sequence is gapless per object.
        db.execute(
            """INSERT INTO fee_audit_events
                 (object_type, object_id, sequence, action, actor_type, actor_id,
                  on_behalf_of, before, after, reason_code, reason, request_id,
                  occurred_at, recorded_at)
               SELECT 'fee', %s,
                      COALESCE(MAX(sequence), 0) + 1, 'update_fee', %s, %s,
                      %s, %s::jsonb, %s::jsonb, %s, %s, %s, now(), now()
               FROM fee_audit_events WHERE object_type = 'fee' AND object_id = %s""",
            (fee_id, actor_type, actor_id, on_behalf_of,
             f'{{"bps": {int(before)}}}', f'{{"bps": {int(bps)}}}',
             reason_code, reason, request_id, fee_id),
        )
