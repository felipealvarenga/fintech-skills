"""Capture a payment and notify downstream systems."""

def capture(db, processor, bus, payment_id: str):
    processor.capture(payment_id)
    db.execute("UPDATE payments SET status = 'captured' WHERE id = %s", (payment_id,))
    db.commit()
    bus.publish("payment.captured", {"payment_id": payment_id})
