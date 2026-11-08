"""New money module to be tested."""
from decimal import Decimal, ROUND_HALF_EVEN

EXPONENTS = {"USD": 2, "BRL": 2, "JPY": 0, "BHD": 3}


def to_minor(amount: str, currency: str) -> int:
    return int(Decimal(amount).scaleb(EXPONENTS[currency]))


def allocate(amount: int, ratios: list[int]) -> list[int]:
    total = sum(ratios)
    shares = [amount * r // total for r in ratios]
    rem = amount - sum(shares)
    order = sorted(range(len(ratios)), key=lambda i: -((amount * ratios[i]) % total))
    for i in order[:rem]:
        shares[i] += 1
    return shares


def apply_rate(amount: int, rate: str) -> int:
    return int((Decimal(amount) * Decimal(rate)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
