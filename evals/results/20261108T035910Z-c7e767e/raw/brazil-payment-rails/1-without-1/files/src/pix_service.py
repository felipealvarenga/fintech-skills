"""Pix payments: one dynamic charge (unique txid) per order.

Flow:
  1. Checkout calls create_pix_charge(db, order) -> returns the BR Code
     ("copia e cola" string, also renderable as a QR) to show the customer.
  2. The PSP/bank notifies us of a received payment (webhook) and the handler
     calls on_pix_received(db, txid, amount_minor, end_to_end_id).
  3. The order is marked paid only if txid and amount match, idempotently.

Required tables (add a migration):
  pix_charges(txid TEXT PRIMARY KEY, order_id BIGINT NOT NULL,
              amount_minor BIGINT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
              end_to_end_id TEXT UNIQUE, created_at TIMESTAMP DEFAULT now())
"""

import os
import re
import secrets

PIX_KEY = os.environ.get("PIX_KEY", "")
MERCHANT_NAME = os.environ.get("PIX_MERCHANT_NAME", "LOJA")
MERCHANT_CITY = os.environ.get("PIX_MERCHANT_CITY", "SAO PAULO")


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def _new_txid() -> str:
    # BCB spec: 26-35 alphanumeric chars.
    return secrets.token_hex(16)  # 32 chars


def build_br_code(txid: str, amount_minor: int) -> str:
    """Build an EMV/BR Code payload for a Pix charge with a fixed amount."""
    if not PIX_KEY:
        raise RuntimeError("PIX_KEY is not configured")
    if not re.fullmatch(r"[A-Za-z0-9]{26,35}", txid):
        raise ValueError("invalid txid")
    if amount_minor <= 0:
        raise ValueError("amount must be positive")

    merchant_account = _tlv("00", "br.gov.bcb.pix") + _tlv("01", PIX_KEY)
    payload = (
        _tlv("00", "01")
        + _tlv("26", merchant_account)
        + _tlv("52", "0000")
        + _tlv("53", "986")  # BRL
        + _tlv("54", f"{amount_minor / 100:.2f}")
        + _tlv("58", "BR")
        + _tlv("59", MERCHANT_NAME[:25])
        + _tlv("60", MERCHANT_CITY[:15])
        + _tlv("62", _tlv("05", txid))
        + "6304"
    )
    return payload + _crc16(payload)


def create_pix_charge(db, order) -> str:
    """Create a pending Pix charge for the order and return its BR Code."""
    existing = db.query_one(
        "SELECT txid, amount_minor FROM pix_charges WHERE order_id = %s AND status = 'pending'",
        (order.id,),
    )
    if existing and existing.amount_minor == order.total_minor:
        return build_br_code(existing.txid, existing.amount_minor)

    txid = _new_txid()
    db.execute(
        "INSERT INTO pix_charges (txid, order_id, amount_minor, status) VALUES (%s, %s, %s, 'pending')",
        (txid, order.id, order.total_minor),
    )
    return build_br_code(txid, order.total_minor)


def pix_payload_for(order):
    """Kept for existing callers; prefer create_pix_charge(db, order)."""
    raise NotImplementedError("Use create_pix_charge(db, order); static QR no longer supported")


def on_pix_received(db, txid: str, amount_minor: int, end_to_end_id: str) -> bool:
    """Handle a Pix payment notification. Returns True if an order was marked paid.

    The caller (webhook) must authenticate the notification (PSP signature /
    mTLS) before calling this, and should run it in a transaction.
    """
    charge = db.query_one(
        "SELECT * FROM pix_charges WHERE txid = %s FOR UPDATE", (txid,)
    )
    if not charge:
        return False
    if charge.status == "paid":
        return False  # duplicate notification; idempotent
    if charge.amount_minor != amount_minor:
        # Wrong amount: do not mark paid; leave for manual review/refund.
        return False

    db.execute(
        "UPDATE pix_charges SET status = 'paid', end_to_end_id = %s WHERE txid = %s",
        (end_to_end_id, txid),
    )
    db.execute(
        "UPDATE orders SET status = 'paid' WHERE id = %s AND status = 'pending'",
        (charge.order_id,),
    )
    return True
