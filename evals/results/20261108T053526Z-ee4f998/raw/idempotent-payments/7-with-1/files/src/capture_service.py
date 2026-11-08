"""Capture a payment and notify downstream systems.

Flow (authorized -> capture_pending -> captured):
  1. Guarded transition to capture_pending, committed before the processor call.
  2. Processor call with a key derived from the payment id (same on every retry).
  3. In ONE transaction: mark captured and insert the payment.captured outbox row.
  4. publish_outbox() relays outbox rows to the bus; consumers dedupe by event_id.

Required schema (besides payments):
  CREATE TABLE outbox (
      event_id     TEXT PRIMARY KEY,
      topic        TEXT NOT NULL,
      payload      TEXT NOT NULL,
      published_at TIMESTAMP NULL
  );
"""
import json


class InvalidState(Exception):
    def __init__(self, payment_id: str, status):
        super().__init__(f"payment {payment_id} is {status}")
        self.payment_id = payment_id
        self.status = status


def capture(db, processor, payment_id: str):
    # 1. Guarded transition; a retry may resume a capture_pending payment.
    cur = db.execute(
        "UPDATE payments SET status = 'capture_pending' "
        "WHERE id = %s AND status = 'authorized'",
        (payment_id,),
    )
    db.commit()
    if cur.rowcount == 0:
        row = db.execute("SELECT status FROM payments WHERE id = %s", (payment_id,)).fetchone()
        status = row[0] if row else None
        if status != "capture_pending":
            raise InvalidState(payment_id, status)

    # 2. Deterministic key. A timeout propagates: the outcome is unknown, so the
    #    payment stays capture_pending for a retry (same key) or the reconciler.
    processor.capture(payment_id, idempotency_key=f"capture:{payment_id}")

    # 3. State change and event in the same transaction.
    try:
        cur = db.execute(
            "UPDATE payments SET status = 'captured' "
            "WHERE id = %s AND status = 'capture_pending'",
            (payment_id,),
        )
        if cur.rowcount == 1:
            db.execute(
                "INSERT INTO outbox (event_id, topic, payload) VALUES (%s, %s, %s) "
                "ON CONFLICT (event_id) DO NOTHING",
                (
                    f"payment.captured:{payment_id}",
                    "payment.captured",
                    json.dumps({"payment_id": payment_id}),
                ),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise


def publish_outbox(db, bus, batch: int = 100) -> int:
    """Relay unpublished outbox rows. At-least-once; consumers dedupe by event_id."""
    rows = db.execute(
        "SELECT event_id, topic, payload FROM outbox "
        "WHERE published_at IS NULL ORDER BY event_id LIMIT %s",
        (batch,),
    ).fetchall()
    for event_id, topic, payload in rows:
        bus.publish(topic, {**json.loads(payload), "event_id": event_id})
        db.execute(
            "UPDATE outbox SET published_at = CURRENT_TIMESTAMP WHERE event_id = %s",
            (event_id,),
        )
        db.commit()
    return len(rows)
