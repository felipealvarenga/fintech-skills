"""Money as integer minor units plus an ISO 4217 currency code.

Rounding policy: ROUND_HALF_EVEN by default, named and applied once, where a value
leaves a calculation (apply_rate, convert). Allocation never rounds; it distributes
whole units with the largest-remainder method.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext,
)

# The only exponent table. Extend deliberately; unknown currencies are refused.
EXPONENTS: dict[str, int] = {
    "BRL": 2, "USD": 2, "EUR": 2, "GBP": 2,
    "JPY": 0, "KRW": 0, "CLP": 0,
    "BHD": 3, "KWD": 3, "TND": 3,
}

DEFAULT_ROUNDING = ROUND_HALF_EVEN


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency!r}") from None


def _dec(value) -> Decimal:
    """Decimals come from str/int/Decimal only, never float."""
    if isinstance(value, float):
        raise TypeError("floats are not accepted; pass a str, int or Decimal")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid decimal: {value!r}") from None
    if not d.is_finite():
        raise ValueError(f"non-finite decimal: {value!r}")
    return d


def to_minor(text: str, currency: str) -> int:
    """Parse a decimal string like "12.34" into minor units. Too many decimals is an error."""
    if not isinstance(text, str):
        raise TypeError("amount must be a decimal string")
    exp = exponent(currency)
    d = _dec(text)
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{text!r} has more than {exp} decimals for {currency}")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    """Integer minor units to a plain decimal string ("12.34")."""
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise TypeError("minor units must be an int")
    exp = exponent(currency)
    return format(Decimal(minor).scaleb(-exp), f".{exp}f")


def apply_rate(minor: int, rate: str | Decimal, rounding: str = DEFAULT_ROUNDING) -> int:
    """Multiply minor units by a decimal rate, rounding once with the named policy."""
    with localcontext() as ctx:
        ctx.prec = 50
        result = Decimal(minor) * _dec(rate)
        return int(result.quantize(Decimal(1), rounding=rounding))


def convert(minor: int, src: str, dst: str, rate: str | Decimal,
            rounding: str = DEFAULT_ROUNDING) -> int:
    """Convert using an explicit rate (dst major units per src major unit).

    The caller records the rate, its source and timestamp beside the result.
    """
    with localcontext() as ctx:
        ctx.prec = 50
        major = Decimal(minor).scaleb(-exponent(src))
        target = (major * _dec(rate)).scaleb(exponent(dst))
        return int(target.quantize(Decimal(1), rounding=rounding))


def allocate(minor: int, ratios: list) -> list[int]:
    """Split `minor` by ratios so the parts always sum to `minor`.

    Largest remainder; ties go to the earlier position. Zero ratios get zero.
    Negative amounts are allocated on their absolute value and the sign is restored.
    """
    if not ratios:
        raise ValueError("ratios must not be empty")
    weights = [_dec(r) for r in ratios]
    if any(w < 0 for w in weights):
        raise ValueError("ratios must be non-negative")
    total_w = sum(weights)
    if total_w == 0:
        raise ValueError("ratios must not all be zero")

    sign = -1 if minor < 0 else 1
    whole = abs(minor)
    with localcontext() as ctx:
        ctx.prec = 60
        exact = [Decimal(whole) * w / total_w for w in weights]
        parts = [int(e.to_integral_value(rounding=ROUND_FLOOR)) for e in exact]
        remainders = [e - p for e, p in zip(exact, parts)]
    leftover = whole - sum(parts)
    order = sorted(range(len(parts)), key=lambda i: (-remainders[i], i))
    for i in order:
        if leftover == 0:
            break
        if weights[i] == 0:
            continue
        parts[i] += 1
        leftover -= 1
    return [sign * p for p in parts]


@dataclass(frozen=True)
class Money:
    minor: int
    currency: str

    def __post_init__(self):
        exponent(self.currency)
        if isinstance(self.minor, bool) or not isinstance(self.minor, int):
            raise TypeError("minor units must be an int")

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money) or other.currency != self.currency:
            raise ValueError("cannot add different currencies; convert explicitly")
        return Money(self.minor + other.minor, self.currency)

    def allocate(self, ratios: list) -> list["Money"]:
        return [Money(p, self.currency) for p in allocate(self.minor, ratios)]

    def __str__(self) -> str:
        return f"{from_minor(self.minor, self.currency)} {self.currency}"
