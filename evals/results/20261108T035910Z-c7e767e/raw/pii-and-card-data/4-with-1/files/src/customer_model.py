"""Customer and payment method models.

Card data policy: the full card number (PAN) and CVV are never stored here,
not even encrypted. Cards are captured by the processor's hosted fields and we
keep only a token plus display metadata. To switch processors, request a
processor-to-processor token migration (PCI-compliant PAN transfer between
the two PCI-certified parties) and store the new token in a new row.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    id: str
    name: str
    email: str
    cpf: str  # government id: encrypt at application level with a KMS key


@dataclass
class PaymentMethod:
    customer_id: str
    brand: str
    last4: str
    token: str
    processor: str  # e.g. "stripe", "adyen"; one row per processor token
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    # Stable, processor-provided card fingerprint for dedup across tokens.
    fingerprint: Optional[str] = None
    # Set on the new row when migrating, pointing at the previous token's row.
    migrated_from_token: Optional[str] = None

    def __post_init__(self) -> None:
        if not (self.last4.isdigit() and len(self.last4) == 4):
            raise ValueError("last4 must be exactly four digits")
