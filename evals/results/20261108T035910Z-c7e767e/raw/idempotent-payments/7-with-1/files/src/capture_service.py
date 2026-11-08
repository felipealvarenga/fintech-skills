"""Capture a payment and notify downstream systems.

The payment.captured event is written to an outbox table in the same
transaction as the status change, then relayed to the bus by
`relay_outbox`. Delivery is at-least-once; consumers dedupe by event_id.

Required schema (unique index makes one event per state change):
    CREATE TABLE outbox (
        event_id     text PRIMARY KEY,
        topic        text NOT NULL,
        payload      jsonb NOT NULL,
        created_at   timestamptz NOT NULL DEFAULT now(),
        published_at timestamptz
    );
"""
import json


class InvalidStateError(Exception):
    def __init__(self, payment_id, status):
        super().__init__(f"payment {payment_id} is {status!r}, cannot capture")
        self.status = status


def capture(db, processor, payment_id: str):
    row = db.execute(
        "SELECT status FROM payments WHERE id = %s FOR UPDATE", (payment_id,)
    ).fetchone()
    if row is None:
        raise LookupError(payment_id)
    if row[0] != "authorized":
        # A second capture is rejected with the current state.
        db.rollback()
        raise InvalidStateError(payment_id, row[0])

    try:
        processor.capture(payment_id)
        # NOTE: a timeout here is an unknown outcome; do not mark failed.
        # The processor wrapper should derive its idempotency key from payment_id.
        cur = db.execute(
            "UPDATE payments SET status = 'captured' "
            "WHERE id = %s AND status = 'authorized'",
            (payment_id,),
        )
        if cur.rowcount != 1:
            raise InvalidStateError(payment_id, "changed concurrently")
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


def relay_outbox(db, bus, batch_size: int = 100) -> int:
    """Publish unpublished outbox rows. Run from a worker loop or scheduler.

    A crash after publish but before the update causes a redelivery, which
    is safe because consumers dedupe on event_id.
    """
    rows = db.execute(
        "SELECT event_id, topic, payload FROM outbox "
        "WHERE published_at IS NULL ORDER BY created_at "
        "LIMIT %s FOR UPDATE SKIP LOCKED",
        (batch_size,),
    ).fetchall()
    for event_id, topic, payload in rows:
        body = payload if isinstance(payload, dict) else json.loads(payload)
        bus.publish(topic, {**body, "event_id": event_id})
        db.execute(
            "UPDATE outbox SET published_at = now() WHERE event_id = %s",
            (event_id,),
        )
    db.commit()
    return len(rows)
