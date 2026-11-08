"""Invoice splitting. Amounts are integer cents (BRL)."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, InvalidOperation


@dataclass
class Invoice:
    id: str
    total_cents: int


def split_invoice(total_cents: int, ratios: list[Decimal]) -> list[int]:
    """Split cents by ratios (which must sum to 1); the parts always sum to total_cents.

    Uses the largest-remainder method so no cent is lost or created.
    """
    ratios = [Decimal(str(r)) for r in ratios]
    if not ratios or any(r < 0 for r in ratios) or sum(ratios) != 1:
        raise ValueError("ratios must be non-negative and sum to 1")
    exact = [Decimal(total_cents) * r for r in ratios]
    parts = [int(x.to_integral_value(rounding=ROUND_DOWN)) for x in exact]
    leftover = total_cents - sum(parts)
    order = sorted(range(len(parts)), key=lambda i: exact[i] - parts[i], reverse=True)
    for i in order[:leftover]:
        parts[i] += 1
    return parts


def to_cents(amount: str) -> int:
    try:
        value = Decimal(amount.strip())
    except (InvalidOperation, AttributeError) as e:
        raise ValueError(f"invalid amount: {amount!r}") from e
    if not value.is_finite():
        raise ValueError(f"invalid amount: {amount!r}")
    return int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
