"""Price input parsing. TODO: handle Brazilian and US formats."""

def parse_price(text: str) -> float:
    return float(text.replace(",", ""))
