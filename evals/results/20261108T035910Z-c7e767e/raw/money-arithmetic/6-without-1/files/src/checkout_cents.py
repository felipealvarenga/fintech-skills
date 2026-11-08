"""Checkout totals in minor units, aware of per-currency decimal places (ISO 4217)."""
from decimal import Decimal, ROUND_HALF_UP

# Currencies that don't use 2 decimals. Anything not listed defaults to 2.
CURRENCY_EXPONENTS = {
    "JPY": 0,  # Japanese yen
    "KWD": 3,  # Kuwaiti dinar
}
DEFAULT_EXPONENT = 2


def exponent_for(currency: str) -> int:
    return CURRENCY_EXPONENTS.get(currency.upper(), DEFAULT_EXPONENT)


def to_cents(amount: str, currency: str = "USD") -> int:
    """Convert a decimal string to minor units (yen, fils, cents...)."""
    exp = exponent_for(currency)
    return int((Decimal(amount) * 10**exp).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def to_display(cents: int, currency: str = "USD") -> str:
    exp = exponent_for(currency)
    return f"{Decimal(cents).scaleb(-exp):.{exp}f}"
