"""Money helpers: integer minor units, ISO 4217 exponents, decimal-string wire format."""
from decimal import Decimal, InvalidOperation

# The only exponent table. Unknown currencies are refused.
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


def to_minor(value, currency: str) -> int:
    """Parse a decimal string/Decimal/int into minor units. Too many decimals is an error."""
    exp = exponent(currency)
    if isinstance(value, float):
        raise TypeError("floats are not accepted as money")
    try:
        d = Decimal(value) if not isinstance(value, Decimal) else value
    except InvalidOperation:
        raise ValueError(f"invalid amount: {value!r}") from None
    if not d.is_finite():
        raise ValueError("amount must be finite")
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{value!r} has more than {exp} decimals for {currency}")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    """Minor units to a decimal string with exactly `exponent` decimals."""
    exp = exponent(currency)
    if not isinstance(minor, int) or isinstance(minor, bool):
        raise TypeError("minor units must be an int")
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exp + 1, "0")
    if exp == 0:
        return sign + digits
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"
