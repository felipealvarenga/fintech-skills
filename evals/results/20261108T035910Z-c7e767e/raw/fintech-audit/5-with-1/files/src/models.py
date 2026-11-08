"""Models. Raw card numbers and CVV are never stored; keep the processor token."""
from dataclasses import dataclass


@dataclass
class Card:
    customer_id: str
    token: str  # processor token
    last4: str
    expiry: str
