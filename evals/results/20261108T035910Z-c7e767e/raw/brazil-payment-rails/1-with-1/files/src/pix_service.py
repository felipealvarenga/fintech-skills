"""Pix checkout: one dynamic charge (cobrança imediata) per order.

Rules followed (brazil-payment-rails):
- we choose the txid, the system assigns endToEndId; both are stored and unique
- reconciliation is by txid, never by payer name or amount
- a webhook is only a notification: the charge is confirmed through the PSP API
- paid-after-expiry, wrong amount or already-paid charges are refunded (devolução)
- a received Pix can still be clawed back (MED), so 'paid' is not terminal
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

CHARGE_TTL_SECONDS = 15 * 60


class PixPSP(Protocol):
    def create_immediate_charge(self, txid: str, amount_minor: int, expires_in: int) -> str:
        """Create the charge and return the copy-and-paste BR Code payload."""

    def get_charge(self, txid: str) -> dict:
        """Return {'status': 'ATIVA'|'CONCLUIDA'|'REMOVIDA_PELO_USUARIO_RECEBEDOR'|
        'REMOVIDA_PELO_PSP', 'amount_minor': int, 'paid_end_to_end_ids': [str]}."""

    def refund(self, end_to_end_id: str, refund_id: str, amount_minor: int) -> None:
        """Request a devolução against the original endToEndId."""


def new_txid() -> str:
    return uuid.uuid4().hex  # 32 chars, [a-z0-9]: valid Pix txid (26-35 alphanumeric)


def create_charge(db, psp: PixPSP, order) -> dict:
    """Create (or reuse the active) Pix charge for an order. Returns txid + payload."""
    now = datetime.now(timezone.utc)
    existing = db.query_one(
        "SELECT * FROM pix_charges WHERE order_id = %s AND status = 'active' AND expires_at > %s",
        (order.id, now.isoformat()),
    )
    if existing:
        return {"txid": existing.txid, "payload": existing.payload}

    txid = new_txid()
    payload = psp.create_immediate_charge(txid, order.total_minor, CHARGE_TTL_SECONDS)
    db.execute(
        "INSERT INTO pix_charges (txid, order_id, amount_minor, payload, status, expires_at) "
        "VALUES (%s, %s, %s, %s, 'active', %s)",
        (txid, order.id, order.total_minor, payload,
         (now + timedelta(seconds=CHARGE_TTL_SECONDS)).isoformat()),
    )
    return {"txid": txid, "payload": payload}


def pix_payload_for(db, psp: PixPSP, order) -> str:
    return create_charge(db, psp, order)["payload"]


def on_pix_received(db, psp: PixPSP, txid: str, end_to_end_id: str, amount_minor: int) -> str:
    """Handle a 'Pix received' webhook. Returns 'paid', 'duplicate', 'refunded' or 'unknown_charge'.

    Idempotent on end_to_end_id. The order is marked paid only if the PSP API confirms the
    charge is settled for exactly the expected amount.
    """
    if db.query_one("SELECT 1 AS x FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,)):
        return "duplicate"

    charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (txid,))
    if charge is None:
        _record(db, end_to_end_id, txid, amount_minor, "unknown_charge")
        return "unknown_charge"  # no order to credit; ops reviews, funds not silently kept

    remote = psp.get_charge(txid)  # confirm through the API, do not trust the webhook body
    already_paid = charge.status == "paid"
    settled = remote["status"] == "CONCLUIDA" and end_to_end_id in remote.get("paid_end_to_end_ids", [])
    exact = amount_minor == charge.amount_minor and remote.get("amount_minor") == charge.amount_minor
    expired = charge.status == "expired" or remote["status"] != "CONCLUIDA"

    if settled and exact and not already_paid and not expired:
        _record(db, end_to_end_id, txid, amount_minor, "paid")
        db.execute("UPDATE pix_charges SET status = 'paid', end_to_end_id = %s WHERE txid = %s",
                   (end_to_end_id, txid))
        db.execute("UPDATE orders SET status = 'paid' WHERE id = %s AND status = 'pending'",
                   (charge.order_id,))
        return "paid"

    # Expired, repeated, over/under payment, or not confirmed: refund by policy.
    _record(db, end_to_end_id, txid, amount_minor, "refund_requested")
    psp.refund(end_to_end_id, "r" + end_to_end_id, amount_minor)
    return "refunded"


def expire_charges(db, now: datetime | None = None) -> None:
    """Run periodically: stop offering charges past their expiry."""
    now = now or datetime.now(timezone.utc)
    db.execute("UPDATE pix_charges SET status = 'expired' WHERE status = 'active' AND expires_at <= %s",
               (now.isoformat(),))


def _record(db, end_to_end_id, txid, amount_minor, outcome):
    db.execute(
        "INSERT INTO pix_payments (end_to_end_id, txid, amount_minor, outcome) VALUES (%s, %s, %s, %s)",
        (end_to_end_id, txid, amount_minor, outcome),
    )
