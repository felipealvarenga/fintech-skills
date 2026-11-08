"""Models. Card data stays with the processor; we keep only a token and display fields."""
from dataclasses import dataclass


@dataclass
class Card:
    customer_id: str
    token: str  # processor token from hosted fields
    last4: str
    brand: str
    expiry: str
    # No PAN, no CVV: never stored.
