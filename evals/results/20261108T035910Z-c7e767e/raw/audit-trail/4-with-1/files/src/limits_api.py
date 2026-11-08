"""Admin endpoint: change a customer's transfer limit.

Audit design: the audit event is inserted in the SAME transaction as the limit
change (audit-trail rule 1: no best-effort audit, no after-commit write). That
insert is a single append-only row, so it is cheap. The slow work (shipping the
event to the external sink, hash-chain digests, search indexing) is moved off
the request path: `publish_pending_audit_events` drains the table after commit.
"""
import json
import uuid
from datetime import datetime, timezone

REASON_CODES = {"customer_request", "risk_review", "fraud_response", "support_ticket", "correction"}


def set_transfer_limit(db, customer_id: str, new_limit_minor: int, *, actor_id: str,
                       reason_code: str, reason_text: str, request_id: str,
                       actor_type: str = "user", on_behalf_of: str | None = None):
    if reason_code not in REASON_CODES:
        raise ValueError(f"reason_code must be one of {sorted(REASON_CODES)}")
    if not reason_text:
        raise ValueError("reason_text (or ticket reference) is required")

    try:
        # Lock the row so before/after and the per-object sequence are consistent.
        row = db.execute("SELECT transfer_limit FROM customers WHERE id = %s FOR UPDATE",
                         (customer_id,)).fetchone()
        if row is None:
            raise LookupError(f"customer {customer_id} not found")
        before = row[0]

        db.execute("UPDATE customers SET transfer_limit = %s WHERE id = %s",
                   (new_limit_minor, customer_id))

        seq = db.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_events "
                         "WHERE object_type = 'customer_limit' AND object_id = %s",
                         (customer_id,)).fetchone()[0]

        # Same transaction: if this fails, the limit change rolls back.
        db.execute(
            "INSERT INTO audit_events (event_id, object_type, object_id, sequence, action, "
            "actor_type, actor_id, on_behalf_of, before, after, reason_code, reason_text, "
            "request_id, occurred_at, source, published_at) "
            "VALUES (%s, 'customer_limit', %s, %s, 'set_transfer_limit', %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, 'limits_api', NULL)",   # recorded_at: DB default now()
            (str(uuid.uuid4()), customer_id, seq, actor_type, actor_id, on_behalf_of,
             json.dumps({"transfer_limit": before}), json.dumps({"transfer_limit": new_limit_minor}),
             reason_code, reason_text, request_id, datetime.now(timezone.utc)),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def publish_pending_audit_events(db, sink, batch_size: int = 100) -> int:
    """Async relay (run from a worker/queue consumer after commit).

    Delivers unpublished events to `sink` (queue, SIEM, write-once store) and marks
    them published. At-least-once: `sink` must dedupe on event_id. Never updates
    event content, only the delivery marker (grant the relay role UPDATE on
    `published_at` only, or track delivery in a separate table).
    """
    rows = db.execute("SELECT event_id, row_to_json(a) FROM audit_events a "
                      "WHERE published_at IS NULL ORDER BY recorded_at, sequence "
                      "LIMIT %s FOR UPDATE SKIP LOCKED", (batch_size,)).fetchall()
    for event_id, payload in rows:
        sink.send(event_id, payload)
        db.execute("UPDATE audit_events SET published_at = now() WHERE event_id = %s", (event_id,))
    db.commit()
    return len(rows)
