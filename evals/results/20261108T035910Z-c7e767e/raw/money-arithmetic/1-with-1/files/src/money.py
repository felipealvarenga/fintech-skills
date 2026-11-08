"""Money as integer minor units plus an ISO 4217 currency code.

Rounding policy: ROUND_HALF_EVEN, applied only in apply_rate (the single rounding point).
Allocation uses largest remainder and never rounds.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation

# The only exponent table. Unknown currencies are refused.
EXPONENTS = {"BRL": 2, "USD": 2, "EUR": 2, "JPY": 0, "KRW": 0, "CLP": 0,
             "BHD": 3, "KWD": 3, "TND": 3}


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency!r}") from None


@dataclass(frozen=True)
class Money:
    minor: int
    currency: str

    def __post_init__(self):
        if isinstance(self.minor, bool) or not isinstance(self.minor, int):
            raise TypeError("minor units must be an int")
        exponent(self.currency)

    def __add__(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError("cannot add different currencies")
        return Money(self.minor + other.minor, self.currency)

    def __str__(self) -> str:
        return from_minor(self.minor, self.currency)


def to_minor(text: str, currency: str) -> int:
    """Parse a decimal string. Too many decimals, NaN or infinity are errors."""
    exp = exponent(currency)
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}") from None
    if not d.is_finite():
        raise ValueError(f"invalid amount: {text!r}")
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{text!r} has more than {exp} decimals for {currency}")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    exp = exponent(currency)
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exp + 1, "0")
    if exp == 0:
        return sign + digits
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"


def apply_rate(minor: int, rate: str) -> int:
    """Multiply by a decimal-string rate; round once, HALF_EVEN."""
    return int((Decimal(minor) * Decimal(rate)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def allocate(total: int, ratios: list[int]) -> list[int]:
    """Largest-remainder allocation. Parts always sum to total; zero ratios get zero.

    Ratios are integers (e.g. 50, 30, 20) so no float enters the calculation.
    """
    if not ratios or any(r < 0 for r in ratios) or sum(ratios) == 0:
        raise ValueError("ratios must be non-negative with a positive sum")
    whole = sum(ratios)
    shares = [total * r // whole for r in ratios]  # floor, also for negatives
    leftover = total - sum(shares)
    order = sorted((i for i, r in enumerate(ratios) if r > 0),
                   key=lambda i: (-((total * ratios[i]) % whole), i))
    for k in range(leftover):
        shares[order[k % len(order)]] += 1
    return shares
