"""Charge a card through the processor."""
import uuid
import requests


def charge(customer_id, amount_minor, currency):
    r = requests.post("https://processor.example/charges", headers={"Idempotency-Key": str(uuid.uuid4())},
                      json={"customer": customer_id, "amount": amount_minor, "currency": currency}, timeout=5)
    r.raise_for_status()
    return r.json()
