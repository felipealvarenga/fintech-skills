"""Models."""
from dataclasses import dataclass


@dataclass
class Card:
    customer_id: str
    card_number: str
    cvv: str
    expiry: str
