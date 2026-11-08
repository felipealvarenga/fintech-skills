"""Models."""
from dataclasses import dataclass


@dataclass
class Card:
    """Tokenized card. Never store the PAN or CVV; keep the PSP token and display data only."""
    customer_id: str
    token: str
    last4: str
    expiry: str
