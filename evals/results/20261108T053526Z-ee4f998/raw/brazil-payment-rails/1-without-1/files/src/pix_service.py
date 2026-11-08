"""Pix payments: one BR Code per order, reconciled by txid.

Each order gets a unique txid embedded in its BR Code (EMV field 62/05).
The PSP's payment notification echoes that txid, so we match on it instead
of payer name + amount (which is ambiguous and spoofable).
"""

import re
import secrets
from decimal import Decimal

PIX_KEY = "CHANGE-ME"          # merchant Pix key (configure via settings)
MERCHANT_NAME = "MY STORE"     # max 25 chars
MERCHANT_CITY = "SAO PAULO"    # max 15 chars

_TXID_RE = re.compile(r"^[A-Za-z0-9]{26,35}$")


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16(data: str) -> str:
    """CRC16/CCITT-FALSE as required by the BR Code spec."""
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def new_txid() -> str:
    return secrets.token_hex(16)  # 32 alphanumeric chars


def build_payload(amount_minor: int, txid: str) -> str:
    if amount_minor <= 0:
        raise ValueError("amount must be positive")
    if not _TXID_RE.match(txid):
        raise ValueError("txid must be 26-35 alphanumeric characters")
    amount = f"{Decimal(amount_minor) / 100:.2f}"
    merchant_info = _tlv("00", "br.gov.bcb.pix") + _tlv("01", PIX_KEY)
    body = (
        _tlv("00", "01")
        + _tlv("26", merchant_info)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", amount)
        + _tlv("58", "BR")
        + _tlv("59", MERCHANT_NAME[:25])
        + _tlv("60", MERCHANT_CITY[:15])
        + _tlv("62", _tlv("05", txid))
        + "6304"
    )
    return body + _crc16(body)


def create_pix_charge(db, order):
    """Called at checkout when the customer picks Pix. Returns the copy-and-paste / QR payload."""
    txid = new_txid()
    db.execute(
        "UPDATE orders SET pix_txid = %s, payment_method = 'pix' WHERE id = %s AND status = 'pending'",
        (txid, order.id),
    )
    return {"txid": txid, "payload": build_payload(order.total_minor, txid)}


def on_pix_received(db, txid: str, amount_minor: int) -> bool:
    """Handle a (verified) PSP webhook. Idempotent; returns True if the order was marked paid.

    The webhook endpoint must authenticate the PSP (mTLS / signature) before calling this.
    """
    # Conditional UPDATE keeps this atomic and safe against duplicate deliveries.
    rows = db.execute(
        "UPDATE orders SET status = 'paid' "
        "WHERE pix_txid = %s AND total_minor = %s AND status = 'pending'",
        (txid, amount_minor),
    )
    return bool(rows)
