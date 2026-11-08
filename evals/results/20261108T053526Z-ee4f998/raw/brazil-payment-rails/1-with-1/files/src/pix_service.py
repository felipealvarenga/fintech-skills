"""Pix checkout: one dynamic charge (cobranca imediata) per order.

Reconciliation is by txid and endToEndId, never by payer name or amount.
The order is marked paid only after a webhook is confirmed against the PSP.
Anything unexpected (expired, duplicate payment, wrong amount, unknown txid,
static QR payment) is refunded or parked in pix_exceptions, never credited silently.

Expected `db` API: query_one(sql, params) -> row with attributes or None,
execute(sql, params). Schema: sql/pix.sql. `psp` must implement PixPsp below.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

CHARGE_TTL = timedelta(minutes=30)


class PixPsp(Protocol):
    def create_charge(self, txid: str, amount_minor: int, expires_in_s: int) -> str:
        """Create a cobranca imediata; return the BR Code (copia e cola) payload."""

    def get_charge(self, txid: str) -> dict:
        """Return {'status': 'ACTIVE'|'CONCLUIDA'|'REMOVIDA...', 'amount_minor': int}."""

    def refund(self, end_to_end_id: str, refund_id: str, amount_minor: int) -> None:
        """Request a devolucao (full or partial) against the original endToEndId."""


def _now():
    return datetime.now(timezone.utc)


def create_pix_charge(db, psp: PixPsp, order, now=None) -> dict:
    """Create (or return the active) dynamic charge for an order. Order stays pending."""
    now = now or _now()
    existing = db.query_one(
        "SELECT * FROM pix_charges WHERE order_id = %s AND status = 'active' AND expires_at > %s",
        (order.id, now.isoformat()),
    )
    if existing:
        return {"txid": existing.txid, "payload": existing.payload, "expires_at": existing.expires_at}

    txid = uuid.uuid4().hex  # 32 alphanumeric chars; BCB allows 26-35
    expires_at = now + CHARGE_TTL
    payload = psp.create_charge(txid, order.total_minor, int(CHARGE_TTL.total_seconds()))
    db.execute(
        "INSERT INTO pix_charges (txid, order_id, amount_minor, payload, status, expires_at) "
        "VALUES (%s, %s, %s, %s, 'active', %s)",
        (txid, order.id, order.total_minor, payload, expires_at.isoformat()),
    )
    return {"txid": txid, "payload": payload, "expires_at": expires_at.isoformat()}


def pix_payload_for(order, db, psp):
    return create_pix_charge(db, psp, order)["payload"]


def on_pix_received(db, psp: PixPsp, event: dict, now=None) -> str:
    """Handle a 'Pix received' webhook. event: txid (may be None), end_to_end_id, amount_minor.

    Returns one of: 'paid', 'duplicate', 'refunded', 'exception'.
    """
    now = now or _now()
    e2e = event["end_to_end_id"]
    amount = event["amount_minor"]
    txid = event.get("txid")

    # Idempotency: each endToEndId is processed once (unique index is the backstop).
    if db.query_one("SELECT 1 AS x FROM pix_payments WHERE end_to_end_id = %s", (e2e,)):
        return "duplicate"

    charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (txid,)) if txid else None

    if charge is None:
        # Static QR or unknown txid: no charge to reconcile against.
        _record(db, e2e, txid, None, amount, "exception")
        _exception(db, e2e, txid, "no matching charge (static QR or unknown txid)")
        return "exception"

    # Confirm with the PSP before fulfilling; do not trust the webhook body alone.
    remote = psp.get_charge(charge.txid)
    reason = None
    if charge.status == "paid":
        reason = "charge already paid"
    elif remote.get("status") != "CONCLUIDA":
        reason = "PSP does not confirm charge as paid"
    elif amount != charge.amount_minor or remote.get("amount_minor", amount) != amount:
        reason = "amount differs from charge"
    elif datetime.fromisoformat(charge.expires_at) < now and charge.status != "active":
        reason = "charge expired"
    elif charge.status == "expired":
        reason = "charge expired"

    if reason is None:
        _record(db, e2e, charge.txid, charge.order_id, amount, "paid")
        db.execute("UPDATE pix_charges SET status = 'paid', end_to_end_id = %s WHERE txid = %s",
                   (e2e, charge.txid))
        db.execute("UPDATE orders SET status = 'paid' WHERE id = %s AND status = 'pending'",
                   (charge.order_id,))
        return "paid"

    # Anything else: full devolucao by policy, and log it for ops.
    _record(db, e2e, charge.txid, charge.order_id, amount, "refunded")
    _exception(db, e2e, charge.txid, reason)
    refund_pix(db, psp, e2e, amount, reason="auto: " + reason)
    return "refunded"


def refund_pix(db, psp: PixPsp, end_to_end_id: str, amount_minor: int, reason: str = "") -> str:
    """Full or partial devolucao against the original endToEndId. Never exceeds what was received."""
    pay = db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,))
    if pay is None:
        raise ValueError("unknown endToEndId")
    if amount_minor <= 0 or pay.refunded_minor + amount_minor > pay.amount_minor:
        raise ValueError("refund exceeds received amount")
    refund_id = uuid.uuid4().hex
    psp.refund(end_to_end_id, refund_id, amount_minor)
    db.execute("INSERT INTO pix_refunds (refund_id, end_to_end_id, amount_minor, reason) VALUES (%s, %s, %s, %s)",
               (refund_id, end_to_end_id, amount_minor, reason))
    db.execute("UPDATE pix_payments SET refunded_minor = refunded_minor + %s WHERE end_to_end_id = %s",
               (amount_minor, end_to_end_id))
    return refund_id


def expire_charges(db, now=None):
    now = now or _now()
    db.execute("UPDATE pix_charges SET status = 'expired' WHERE status = 'active' AND expires_at <= %s",
               (now.isoformat(),))


def _record(db, e2e, txid, order_id, amount, outcome):
    db.execute(
        "INSERT INTO pix_payments (end_to_end_id, txid, order_id, amount_minor, refunded_minor, outcome) "
        "VALUES (%s, %s, %s, %s, 0, %s)",
        (e2e, txid, order_id, amount, outcome),
    )


def _exception(db, e2e, txid, reason):
    db.execute("INSERT INTO pix_exceptions (end_to_end_id, txid, reason) VALUES (%s, %s, %s)",
               (e2e, txid, reason))
