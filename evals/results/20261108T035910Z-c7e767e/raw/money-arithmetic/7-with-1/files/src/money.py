"""Currency exponent table (ISO 4217). The only one in the codebase."""

EXPONENTS = {
    "USD": 2, "EUR": 2, "BRL": 2, "GBP": 2,
    "JPY": 0, "KRW": 0, "CLP": 0,
    "BHD": 3, "KWD": 3, "TND": 3,
}


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise ValueError(f"unknown currency: {currency!r}") from None
