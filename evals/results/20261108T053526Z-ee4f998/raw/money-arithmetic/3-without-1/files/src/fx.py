"""FX helpers. Rates come from a daily table."""
RATES = {("USD", "BRL"): 5.1234, ("USD", "JPY"): 150.5}


def convert(amount: float, src: str, dst: str) -> float:
    return round(amount * RATES[(src, dst)], 2)


def convert_usd_to_jpy(amount: float) -> float:
    """Convert USD to JPY using the USD/JPY rate from RATES (150.5)."""
    return convert(amount, "USD", "JPY")
