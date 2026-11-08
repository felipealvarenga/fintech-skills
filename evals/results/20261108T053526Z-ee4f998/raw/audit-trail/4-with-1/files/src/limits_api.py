"""Admin endpoint: change a customer's transfer limit.

The audit event is written in the same transaction as the change (append-only
table, one narrow INSERT). Only slow downstream fan-out is asynchronous, and it
runs after commit from the already-durable event id.
"""
import json
import logging
import uuid

log = logging.getLogger(__name__)

REASON_CODES = {"customer_request", "risk_review", "kyc_update", "correction", "other"}


def set_transfer_limit(db, customer_id: str, new_limit_minor: int, *, actor_id: str,
                       reason_code: str, request_id: str, reason_text: str = "",
                       actor_type: str = "user", on_behalf_of: str | None = None,
                       publish=None):
    if reason_code not in REASON_CODES:
        raise ValueError("invalid reason_code")
    if not actor_id or not request_id:
        raise ValueError("actor_id and request_id are required")

    event_id = str(uuid.uuid4())
    try:
        # Row lock serializes writers per customer, so sequence is gapless.
        row = db.execute(
            "SELECT transfer_limit FROM customers WHERE id = %s FOR UPDATE", (customer_id,)
        ).fetchone()
        if row is None:
            raise LookupError("customer not found")
        before = row[0]

        db.execute("UPDATE customers SET transfer_limit = %s WHERE id = %s",
                   (new_limit_minor, customer_id))
        db.execute(
            """INSERT INTO audit_events
               (event_id, object_type, object_id, sequence, action, actor_type, actor_id,
                on_behalf_of, before, after, reason_code, reason_text, request_id,
                occurred_at, recorded_at)
               VALUES (%s, 'customer', %s,
                       (SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_events
                         WHERE object_type = 'customer' AND object_id = %s),
                       'set_transfer_limit', %s, %s, %s, %s, %s, %s, %s, %s,
                       now() AT TIME ZONE 'utc', now())""",
            (event_id, customer_id, customer_id, actor_type, actor_id, on_behalf_of,
             json.dumps({"transfer_limit": before}),
             json.dumps({"transfer_limit": new_limit_minor}),
             reason_code, reason_text, request_id),
        )
        db.commit()
    except Exception:
        db.rollback()  # a failed event write rolls back the limit change
        raise

    # Async, after commit, best effort: the durable record already exists.
    if publish is not None:
        try:
            publish({"event_id": event_id})
        except Exception:
            log.exception("audit fan-out publish failed for %s", event_id)
    return event_id
