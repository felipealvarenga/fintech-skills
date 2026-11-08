"""Money primitives: integer minor units, ISO 4217 exponents, one rounding policy."""
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

# The single exponent table (ISO 4217). Unknown currencies are refused.
EXPONENTS = {"USD": 2, "EUR": 2, "BRL": 2, "JPY": 0, "KRW": 0, "CLP": 0,
             "BHD": 3, "KWD": 3, "TND": 3}

# The single named rounding policy, applied once when a value leaves a calculation.
ROUNDING = ROUND_HALF_EVEN


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency!r}") from None


def to_minor(text: str, currency: str) -> int:
    """Parse a decimal string; more decimals than the exponent allows is an error."""
    exp = exponent(currency)
    d = Decimal(text)
    if not d.is_finite():
        raise ValueError("amount must be finite")
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{text!r} has more than {exp} decimals for {currency}")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    exp = exponent(currency)
    return format(Decimal(minor).scaleb(-exp), f".{exp}f")


def convert_minor(minor: int, src: str, dst: str, rate: Decimal) -> int:
    """Convert integer minor units src -> dst at `rate` (dst per 1 src, major units).

    Rounds once, with ROUNDING, into the target exponent.
    """
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise TypeError("amount must be an int count of minor units")
    if not isinstance(rate, Decimal):
        raise TypeError("rate must be a Decimal")
    shift = exponent(dst) - exponent(src)
    with localcontext() as ctx:
        ctx.prec = 50
        value = Decimal(minor) * rate * (Decimal(10) ** shift)
        return int(value.quantize(Decimal(1), rounding=ROUNDING))
