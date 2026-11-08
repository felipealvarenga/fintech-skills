"""Customer and payment method models."""
import base64
import os
from dataclasses import dataclass, field
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_key() -> bytes:
    """Load the 256-bit data-encryption key.

    The key must come from a KMS/HSM or secrets manager, never from the repo or
    the same database as the ciphertext. The env var is a stand-in for that
    integration (e.g. envelope encryption with AWS KMS / GCP KMS / Vault).
    """
    raw = os.environ.get("PAN_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError("PAN_ENCRYPTION_KEY is not configured")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("PAN_ENCRYPTION_KEY must be 32 bytes (base64-encoded)")
    return key


def encrypt_pan(pan: str, customer_id: str, key_id: str = "v1") -> str:
    """Encrypt a card number. Output: '<key_id>:<base64(nonce||ciphertext)>'.

    customer_id is bound as associated data so ciphertext can't be moved
    between records. key_id supports key rotation.
    """
    digits = "".join(ch for ch in pan if ch.isdigit())
    if not 13 <= len(digits) <= 19:
        raise ValueError("invalid card number length")
    nonce = os.urandom(12)
    ct = AESGCM(_load_key()).encrypt(nonce, digits.encode(), customer_id.encode())
    return f"{key_id}:{base64.b64encode(nonce + ct).decode()}"


def decrypt_pan(blob: str, customer_id: str) -> str:
    """Decrypt a stored card number. Restrict and audit-log every caller."""
    _key_id, payload = blob.split(":", 1)
    data = base64.b64decode(payload)
    nonce, ct = data[:12], data[12:]
    return AESGCM(_load_key()).decrypt(nonce, ct, customer_id.encode()).decode()


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
    pan_encrypted: Optional[str] = field(default=None, repr=False)

    @classmethod
    def create(cls, customer_id: str, brand: str, pan: str, token: str) -> "PaymentMethod":
        """Build a PaymentMethod from a raw PAN; only last4 + ciphertext are kept.

        Never persist the CVV/CVC, even encrypted (PCI DSS 3.3).
        """
        digits = "".join(ch for ch in pan if ch.isdigit())
        return cls(
            customer_id=customer_id,
            brand=brand,
            last4=digits[-4:],
            token=token,
            pan_encrypted=encrypt_pan(digits, customer_id),
        )

    def reveal_pan(self) -> str:
        if not self.pan_encrypted:
            raise ValueError("no stored PAN")
        return decrypt_pan(self.pan_encrypted, self.customer_id)
