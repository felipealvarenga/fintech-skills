"""Money basics: ISO 4217 exponent table (the only one) and canonical decimal-string parsing."""
import re

EXPONENTS = {
    "USD": 2, "EUR": 2, "BRL": 2, "GBP": 2,
    "JPY": 0, "KRW": 0, "CLP": 0,
    "BHD": 3, "KWD": 3, "TND": 3,
}

_CANONICAL = re.compile(r"^(-?)(\d+)(?:\.(\d+))?$")


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency!r}") from None


def to_minor(text: str, currency: str) -> int:
    """Canonical decimal string ('12.34', '-5', '1000') -> integer minor units.

    Refuses more decimals than the currency allows (no silent rounding).
    """
    exp = exponent(currency)
    m = _CANONICAL.match(text)
    if not m:
        raise ValueError(f"invalid amount: {text!r}")
    sign, whole, frac = m.group(1), m.group(2), m.group(3) or ""
    if len(frac) > exp:
        raise ValueError(f"{text!r} has more than {exp} decimals for {currency}")
    value = int(whole + frac.ljust(exp, "0"))
    return -value if sign else value


def from_minor(minor: int, currency: str) -> str:
    exp = exponent(currency)
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exp + 1, "0")
    if exp == 0:
        return sign + digits
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"
