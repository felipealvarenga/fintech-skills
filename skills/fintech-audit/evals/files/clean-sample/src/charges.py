"""Charges with derived idempotency keys."""


def charge(processor, order):
    key = f"{order.tenant}:charge:{order.id}"
    return processor.charge(idempotency_key=key, amount_minor=order.amount_minor)
