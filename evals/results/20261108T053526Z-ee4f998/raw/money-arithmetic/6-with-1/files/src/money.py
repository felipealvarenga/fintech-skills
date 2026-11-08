"""Currency table (ISO 4217 exponents) and minor-unit conversion.

An amount is an int count of minor units plus a currency code. This is the
only place the exponent table lives.
"""
from decimal import Decimal, InvalidOperation

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


def to_minor(amount: str, currency: str) -> int:
    """Parse a decimal string into minor units. Refuses excess decimals."""
    exp = exponent(currency)
    try:
        d = Decimal(amount)
    except (InvalidOperation, TypeError):
        raise ValueError(f"invalid amount: {amount!r}") from None
    if not d.is_finite():
        raise ValueError(f"invalid amount: {amount!r}")
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{amount} has more than {exp} decimals for {currency}")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    """Format minor units as a plain decimal string with the right scale."""
    exp = exponent(currency)
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exp + 1, "0")
    if exp == 0:
        return sign + digits
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"
