"""Clean money helpers: integer minor units, ISO exponents, one rounding point."""
from decimal import ROUND_HALF_EVEN, Decimal

EXPONENTS = {"BRL": 2, "USD": 2, "JPY": 0}


def to_minor(amount: str, currency: str) -> int:
    exp = EXPONENTS[currency]
    return int(Decimal(amount).scaleb(exp))


def apply_rate(amount_minor: int, rate: str) -> int:
    return int((Decimal(amount_minor) * Decimal(rate)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
