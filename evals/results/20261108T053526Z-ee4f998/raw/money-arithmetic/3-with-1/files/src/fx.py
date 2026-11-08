"""FX helpers. Rates come from a daily table.

Amounts are integer minor units (USD cents, whole JPY); rates are Decimals
built from strings, never floats.
"""
from decimal import Decimal

from money import convert_minor

RATES = {("USD", "BRL"): Decimal("5.1234"), ("USD", "JPY"): Decimal("150.5")}


def convert(minor: int, src: str, dst: str) -> int:
    """Convert integer minor units of `src` into integer minor units of `dst`."""
    return convert_minor(minor, src, dst, RATES[(src, dst)])


def convert_usd_to_jpy(amount: int) -> int:
    """USD cents -> JPY (JPY has 0 decimals), at the table rate, rounded HALF_EVEN once."""
    return convert(amount, "USD", "JPY")
