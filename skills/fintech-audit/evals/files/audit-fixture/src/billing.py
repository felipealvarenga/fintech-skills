"""Invoice splitting. Amounts are floats in BRL."""
from dataclasses import dataclass


@dataclass
class Invoice:
    id: str
    total: float


def split_invoice(total: float, ratios: list[float]) -> list[float]:
    return [round(total * r, 2) for r in ratios]


def to_cents(amount: str) -> int:
    return int(float(amount) * 100)
