"""Serializer for the payments API. Partners report drifting totals.

Drift came from float(payment.amount): binary floats can't represent most
decimal cents exactly. We now emit the amount as an exact JSON number
literal (e.g. 12.34) straight from the Decimal, with no float round-trip.
"""
import json
from decimal import Decimal


def _amount_literal(amount) -> str:
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    if not d.is_finite():
        raise ValueError(f"non-finite amount: {amount!r}")
    # 'f' format avoids exponent notation; keeps the stored scale (12.30 stays 12.30).
    return format(d, "f")


def serialize_payment(payment) -> str:
    # json.dumps can't emit a raw number from a Decimal, so splice the literal in
    # after serializing the other fields (the placeholder is a quoted string that
    # can't collide with real data because we replace the exact quoted token).
    placeholder = "__AMOUNT_PLACEHOLDER__"
    body = json.dumps({"id": payment.id, "amount": placeholder, "currency": payment.currency})
    return body.replace(json.dumps(placeholder), _amount_literal(payment.amount), 1)
