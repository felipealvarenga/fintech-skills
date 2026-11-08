"""Money helpers: integer minor units, ISO 4217 exponents, strict parsing."""
from decimal import Decimal, InvalidOperation

# The only exponent table. Extend per ISO 4217; unknown currencies are refused.
EXPONENTS = {
    "USD": 2, "EUR": 2, "BRL": 2, "GBP": 2,
    "JPY": 0, "KRW": 0, "CLP": 0,
    "BHD": 3, "KWD": 3, "TND": 3,
}


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency!r}") from None


def to_minor(amount, currency: str) -> int:
    """Parse a str/int/Decimal into minor units. Floats and extra decimals are errors."""
    exp = exponent(currency)
    if isinstance(amount, float):
        raise TypeError("float amounts are not accepted")
    try:
        d = Decimal(amount) if not isinstance(amount, Decimal) else amount
    except InvalidOperation:
        raise ValueError(f"invalid amount: {amount!r}") from None
    if not d.is_finite():
        raise ValueError("amount must be finite")
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{amount} has more than {exp} decimals for {currency}")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    """Exact decimal string, e.g. from_minor(1234, 'USD') == '12.34'."""
    exp = exponent(currency)
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exp + 1, "0")
    if exp == 0:
        return sign + digits
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"
