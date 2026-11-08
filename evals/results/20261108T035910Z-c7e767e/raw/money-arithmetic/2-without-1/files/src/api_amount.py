"""Serializer for the payments API. Partners report drifting totals."""
import json
from decimal import Decimal


def serialize_payment(payment) -> str:
    # Never go through float: emit the exact decimal value as a JSON number
    # literal (e.g. 12.34) so no binary rounding is introduced on our side.
    amount = payment.amount
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if not amount.is_finite():
        raise ValueError(f"non-finite amount: {amount}")
    amount_literal = format(amount, "f")
    head = json.dumps({"id": payment.id})[:-1]
    return f'{head}, "amount": {amount_literal}, "currency": {json.dumps(payment.currency)}}}'
