"""Serializer for the payments API.

Wire format: "amount" is a decimal STRING in major units ("12.34"), never a JSON
number, so partners cannot parse it into a binary float. Decimals always match
the currency's ISO 4217 exponent (JPY "1234", BHD "1.234").
"""
import json

from money import from_minor, to_minor


def serialize_payment(payment) -> str:
    # payment.amount is expected to be a Decimal/str in major units (never float).
    # to_minor validates currency and decimals; from_minor emits the canonical string.
    minor = to_minor(payment.amount, payment.currency)
    return json.dumps({
        "id": payment.id,
        "amount": from_minor(minor, payment.currency),
        "currency": payment.currency,
    })
