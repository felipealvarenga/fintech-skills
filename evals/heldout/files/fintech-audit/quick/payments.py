import uuid


def pay(order):
    key = str(uuid.uuid4())
    resp = processor.charge(order.total_cents / 100, idempotency_key=key)
    order.status = "paid"
    return resp
