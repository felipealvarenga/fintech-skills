"""Checkout totals. Amounts are integer minor units; the exponent comes from ISO 4217."""
from decimal import Decimal, InvalidOperation

# The only exponent table. Unknown currencies are refused.
EXPONENTS = {
    "USD": 2,
    "EUR": 2,
    "BRL": 2,
    "JPY": 0,
    "KWD": 3,
}


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unsupported currency: {currency!r}") from None


def to_cents(amount: str, currency: str) -> int:
    """Parse a decimal string into integer minor units. Never rounds."""
    exp = exponent(currency)
    if not isinstance(amount, str):
        raise TypeError("amount must be a decimal string, not a float")
    try:
        d = Decimal(amount)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {amount!r}") from None
    if not d.is_finite():
        raise ValueError(f"invalid amount: {amount!r}")
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{amount!r} has more than {exp} decimals for {currency}")
    return int(scaled)


def to_display(cents: int, currency: str) -> str:
    """Format integer minor units as a plain decimal string (no locale)."""
    exp = exponent(currency)
    sign = "-" if cents < 0 else ""
    q, r = divmod(abs(cents), 10 ** exp)
    return f"{sign}{q}" if exp == 0 else f"{sign}{q}.{r:0{exp}d}"
