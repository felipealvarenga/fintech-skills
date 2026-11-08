"""Checkout totals in integer minor units. Exponent comes from money.EXPONENTS."""
from money import from_minor, to_minor


def to_cents(amount: str, currency: str) -> int:
    return to_minor(amount, currency)


def to_display(minor: int, currency: str) -> str:
    return from_minor(minor, currency)
