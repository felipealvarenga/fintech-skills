"""Invoice splitting. Amounts are integer minor units (centavos, BRL)."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN


@dataclass
class Invoice:
    id: str
    total_cents: int


def split_invoice(total_cents: int, ratios: list[Decimal]) -> list[int]:
    """Largest-remainder allocation: parts always sum exactly to total_cents."""
    if total_cents < 0 or not ratios:
        raise ValueError("invalid total or ratios")
    ratios = [Decimal(r) for r in ratios]
    if any(r < 0 for r in ratios) or sum(ratios) != 1:
        raise ValueError("ratios must be non-negative and sum to 1")
    exact = [Decimal(total_cents) * r for r in ratios]
    parts = [int(e) for e in exact]  # floor (non-negative)
    leftover = total_cents - sum(parts)
    order = sorted(range(len(parts)), key=lambda i: (exact[i] - parts[i], -i), reverse=True)
    for i in order[:leftover]:
        parts[i] += 1
    return parts


def to_cents(amount: str) -> int:
    """Parse a decimal string such as '10.05' to cents without floats."""
    try:
        d = Decimal(amount.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"invalid amount: {amount!r}")
    if not d.is_finite():
        raise ValueError(f"invalid amount: {amount!r}")
    return int((d * 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
