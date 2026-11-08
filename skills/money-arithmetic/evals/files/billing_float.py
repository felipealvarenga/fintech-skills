"""Invoice splitting as it exists today. Amounts are floats in BRL."""

def split_invoice(total: float, ratios: list[float]) -> list[float]:
    return [round(total * r, 2) for r in ratios]


def invoice_total(lines: list[float]) -> float:
    return round(sum(lines), 2)
