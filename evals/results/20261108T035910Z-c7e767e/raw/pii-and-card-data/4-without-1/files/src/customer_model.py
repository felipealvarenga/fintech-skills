"""Customer and payment method models."""
import base64
import os
from dataclasses import dataclass, field
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Keys come from a KMS/HSM-backed secret, never from source control.
# PAN_ENCRYPTION_KEYS format: "key_id1:base64key1,key_id2:base64key2"
# (each key is 32 bytes, base64). The first entry is the active key; the rest
# are retained only for decrypting older records (key rotation).
_KEYS_ENV = "PAN_ENCRYPTION_KEYS"


def _load_keys() -> dict:
    raw = os.environ.get(_KEYS_ENV)
    if not raw:
        raise RuntimeError(f"{_KEYS_ENV} is not set; refusing to handle PAN")
    keys = {}
    for entry in raw.split(","):
        key_id, _, b64 = entry.partition(":")
        key = base64.b64decode(b64)
        if len(key) != 32:
            raise ValueError(f"key {key_id!r} must be 32 bytes")
        keys[key_id] = key
    return keys


def _active_key_id(keys: dict) -> str:
    return next(iter(keys))


def encrypt_pan(pan: str, customer_id: str) -> tuple[str, str]:
    """Encrypt a card number. Returns (key_id, base64 nonce+ciphertext).

    The customer_id is bound as AAD so a ciphertext can't be moved to
    another customer's row.
    """
    digits = "".join(ch for ch in pan if ch.isdigit())
    if not 12 <= len(digits) <= 19:
        raise ValueError("invalid card number length")
    keys = _load_keys()
    key_id = _active_key_id(keys)
    nonce = os.urandom(12)
    ct = AESGCM(keys[key_id]).encrypt(nonce, digits.encode(), customer_id.encode())
    return key_id, base64.b64encode(nonce + ct).decode()


def decrypt_pan(key_id: str, blob: str, customer_id: str) -> str:
    """Decrypt a card number. Callers must be audited/restricted (PCI DSS 3, 7, 10)."""
    keys = _load_keys()
    raw = base64.b64decode(blob)
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(keys[key_id]).decrypt(nonce, ct, customer_id.encode()).decode()


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
    # Encrypted full card number (PAN). Excluded from repr to keep it out of logs.
    pan_encrypted: Optional[str] = field(default=None, repr=False)
    pan_key_id: Optional[str] = field(default=None, repr=False)

    @classmethod
    def create(cls, customer_id: str, brand: str, pan: str, token: str) -> "PaymentMethod":
        """Build a PaymentMethod from a raw PAN; only the encrypted form is kept."""
        key_id, blob = encrypt_pan(pan, customer_id)
        digits = "".join(ch for ch in pan if ch.isdigit())
        return cls(
            customer_id=customer_id,
            brand=brand,
            last4=digits[-4:],
            token=token,
            pan_encrypted=blob,
            pan_key_id=key_id,
        )

    def reveal_pan(self) -> str:
        if not self.pan_encrypted or not self.pan_key_id:
            raise ValueError("no PAN stored for this payment method")
        return decrypt_pan(self.pan_key_id, self.pan_encrypted, self.customer_id)
