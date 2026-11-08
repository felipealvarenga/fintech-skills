"""Customer and payment method models.

Card numbers (PAN) and CVV are never stored here, not even encrypted.
The PAN goes browser -> processor via hosted fields; we keep only the token.
To switch processors, use the processors' PAN/token migration (the old processor
exports to the new one, both PCI-compliant) and write the new token alongside
the old one, keyed by `processor`.
"""
from dataclasses import dataclass, fields

FORBIDDEN_FIELD_NAMES = {"pan", "card_number", "cvv", "cvc", "security_code"}


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
    token: str
    processor: str  # which processor issued `token`; tokens are not portable
    exp_month: int
    exp_year: int

    def to_public(self) -> dict:
        """API/UI representation: no token, last four only."""
        return {
            "brand": self.brand,
            "last4": self.last4,
            "exp_month": self.exp_month,
            "exp_year": self.exp_year,
            "processor": self.processor,
        }


def forbidden_fields(cls) -> set:
    return {f.name for f in fields(cls)} & FORBIDDEN_FIELD_NAMES
