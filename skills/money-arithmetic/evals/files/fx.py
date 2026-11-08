"""FX helpers. Rates come from a daily table."""
RATES = {("USD", "BRL"): 5.1234, ("USD", "JPY"): 150.5}


def convert(amount: float, src: str, dst: str) -> float:
    return round(amount * RATES[(src, dst)], 2)
