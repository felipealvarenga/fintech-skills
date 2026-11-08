"""Serializer for the payments API.

Wire format: "amount" is a decimal STRING in the currency's exact scale
(e.g. "12.34", JPY "1234", BHD "1.234"), never a JSON number, so partners
cannot parse it into a binary float and drift.
"""
import json

from money import from_minor, to_minor


def serialize_payment(payment) -> str:
    minor = to_minor(payment.amount, payment.currency)  # rejects floats / extra decimals
    return json.dumps({
        "id": payment.id,
        "amount": from_minor(minor, payment.currency),
        "currency": payment.currency,
    })
