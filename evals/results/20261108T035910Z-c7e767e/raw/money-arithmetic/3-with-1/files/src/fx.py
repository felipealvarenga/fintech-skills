"""FX helpers. Rates come from a daily table."""
RATES = {("USD", "BRL"): 5.1234, ("USD", "JPY"): 150.5}


def convert(amount: float, src: str, dst: str) -> float:
    return round(amount * RATES[(src, dst)], 2)


from decimal import Decimal, ROUND_HALF_EVEN

USD_JPY_RATE = Decimal("150.5")  # same value as RATES[("USD", "JPY")], kept exact
USD_EXPONENT = 2  # ISO 4217
JPY_EXPONENT = 0  # ISO 4217
ROUNDING = ROUND_HALF_EVEN  # the single rounding policy for this conversion


def convert_usd_to_jpy(amount_minor: int) -> int:
    """Convert USD cents (int) to whole JPY (int), rounding once with ROUND_HALF_EVEN."""
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise TypeError("amount_minor must be an int count of USD cents")
    jpy = Decimal(amount_minor) * USD_JPY_RATE / (Decimal(10) ** (USD_EXPONENT - JPY_EXPONENT))
    return int(jpy.quantize(Decimal(1), rounding=ROUNDING))
