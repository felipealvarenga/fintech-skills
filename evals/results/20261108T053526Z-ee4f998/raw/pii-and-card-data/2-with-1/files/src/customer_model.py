"""Customer and payment method models.

Card data policy: the PAN and CVV never enter our systems. The browser sends
them straight to the processor (hosted fields / SDK), which returns a token.
We keep only the token, brand, last four digits and expiry. One-click payment
charges the saved token; if the processor requires a CVV for a repeat charge,
it is collected again by the processor's hosted field, never stored by us.
"""
from dataclasses import dataclass, fields


@dataclass
class Customer:
    id: str
    name: str
    email: str
    cpf: str


@dataclass
class PaymentMethod:
    customer_id: str
    brand: str
    last4: str
    token: str  # processor token used for one-click payments
    exp_month: int
    exp_year: int

    def __post_init__(self):
        if not (len(self.last4) == 4 and self.last4.isdigit()):
            raise ValueError("last4 must be exactly four digits")
        if not 1 <= self.exp_month <= 12:
            raise ValueError("exp_month must be 1-12")

    def to_public_dict(self) -> dict:
        """API/UI representation: never includes the token."""
        return {
            "brand": self.brand,
            "last4": self.last4,
            "exp_month": self.exp_month,
            "exp_year": self.exp_year,
        }
