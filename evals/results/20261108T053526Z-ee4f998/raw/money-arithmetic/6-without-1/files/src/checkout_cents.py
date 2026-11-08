"""Checkout totals in minor units, using each currency's ISO 4217 exponent."""
from decimal import Decimal, ROUND_HALF_UP

# Number of decimal places in the minor unit. Currencies not listed are rejected
# rather than silently assumed to have two decimals.
CURRENCY_EXPONENTS = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "KWD": 3,
}


def _exponent(currency: str) -> int:
    try:
        return CURRENCY_EXPONENTS[currency.upper()]
    except KeyError:
        raise ValueError(f"Unsupported currency: {currency!r}") from None


def to_cents(amount: str, currency: str) -> int:
    """Convert a decimal string like "12.345" to minor units (e.g. fils for KWD)."""
    exp = _exponent(currency)
    scaled = Decimal(amount) * (10 ** exp)
    return int(scaled.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def to_display(cents: int, currency: str) -> str:
    exp = _exponent(currency)
    return f"{Decimal(cents).scaleb(-exp):.{exp}f}"
