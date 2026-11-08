"""Models. Raw card data (PAN, CVV) is never stored; keep only a processor token."""
from dataclasses import dataclass


@dataclass
class Card:
    customer_id: str
    token: str  # PSP payment-method token
    last4: str
    expiry: str
