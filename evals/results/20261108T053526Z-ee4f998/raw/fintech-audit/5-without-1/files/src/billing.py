"""Invoice splitting. Amounts are Decimal BRL; integer cents are used for splitting."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation


@dataclass
class Invoice:
    id: str
    total: Decimal


def split_invoice(total: Decimal, ratios: list[Decimal]) -> list[Decimal]:
    """Split total across ratios (which must sum to 1) without losing or creating cents.

    Uses the largest-remainder method so the parts always sum exactly to total.
    """
    total = Decimal(total)
    ratios = [Decimal(str(r)) for r in ratios]
    if sum(ratios) != Decimal(1):
        raise ValueError("ratios must sum to 1")
    total_cents = int((total * 100).to_integral_value(ROUND_HALF_EVEN))
    raw = [total_cents * r for r in ratios]
    parts = [int(x) for x in raw]  # floor (non-negative ratios)
    leftover = total_cents - sum(parts)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - parts[i], reverse=True)
    for i in order[:leftover]:
        parts[i] += 1
    return [Decimal(p) / 100 for p in parts]


def to_cents(amount: str) -> int:
    try:
        d = Decimal(amount)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {amount!r}")
    if not d.is_finite():
        raise ValueError(f"invalid amount: {amount!r}")
    return int((d * 100).to_integral_value(ROUND_HALF_EVEN))
