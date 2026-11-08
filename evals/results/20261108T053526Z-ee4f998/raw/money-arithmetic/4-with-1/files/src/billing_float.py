"""Invoice splitting as it exists today. Amounts are floats in BRL."""

from decimal import Decimal


def split_invoice(total: float, ratios: list[float]) -> list[float]:
    return [round(total * r, 2) for r in ratios]


BRL_EXPONENT = 2  # ISO 4217: BRL has 2 decimals


def _to_minor(amount: float) -> int:
    """Float at the edge -> integer centavos. Refuses sub-centavo input."""
    d = Decimal(repr(amount))
    if not d.is_finite():
        raise ValueError(f"invalid amount: {amount!r}")
    scaled = d.scaleb(BRL_EXPONENT)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"more than {BRL_EXPONENT} decimals: {amount!r}")
    return int(scaled)


def invoice_total(lines: list[float]) -> float:
    """Sum in integer centavos (exact); convert back to float only on return."""
    total_minor = sum(_to_minor(line) for line in lines)
    return float(Decimal(total_minor).scaleb(-BRL_EXPONENT))


# Seen in production: invoice_total([0.1, 0.2, 0.3]) == 0.6000000000000001, and
# sum(split_invoice(100.0, [1/3, 1/3, 1/3])) == 99.99.
