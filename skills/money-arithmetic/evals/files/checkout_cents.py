"""Checkout totals. Every currency is assumed to have two decimals."""

def to_cents(amount: str) -> int:
    return int(round(float(amount) * 100))


def to_display(cents: int) -> str:
    return f"{cents / 100:.2f}"
