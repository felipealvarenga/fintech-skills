"""Invoice splitting as it exists today. Amounts are floats in BRL."""

def split_invoice(total: float, ratios: list[float]) -> list[float]:
    return [round(total * r, 2) for r in ratios]


def invoice_total(lines: list[float]) -> float:
    total = 0.0
    for line in lines:
        total += line
    return total


# Seen in production: invoice_total([0.1, 0.2, 0.3]) == 0.6000000000000001, and
# sum(split_invoice(100.0, [1/3, 1/3, 1/3])) == 99.99.
