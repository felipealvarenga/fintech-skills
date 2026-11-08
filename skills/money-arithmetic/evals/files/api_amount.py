"""Serializer for the payments API. Partners report drifting totals."""
import json


def serialize_payment(payment) -> str:
    return json.dumps({"id": payment.id, "amount": float(payment.amount), "currency": payment.currency})
