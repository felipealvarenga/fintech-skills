"""Pix service: dynamic charges, idempotent receipt, devolucao and MED disputes.

Assumed tables (create the migration to match):
  pix_charges(txid PK, order_id, amount_minor, status, expires_at)
      status: open | paid | expired | refund_pending | refunded
  pix_payments(end_to_end_id PK, txid, amount_minor, refunded_minor, status, received_at)
      status: settled | disputed | clawed_back | refunded | exception
  pix_disputes(id, end_to_end_id UNIQUE, opened_at, status, order_shipped, amount_minor)
      status: open | funds_returned | closed_no_loss
  orders.status: pending | paid | disputed | recovery | lost | cancelled
"""
import uuid

# Policy for a Pix that arrives after the charge expired: "refund" or "exception".
EXPIRED_PAYMENT_POLICY = "refund"


def create_charge(db, order, expires_in_s: int = 3600) -> str:
    """Dynamic charge (cobranca imediata). The txid, not name/amount, ties Pix to order."""
    txid = uuid.uuid4().hex  # 32 chars, within the 26-35 alphanumeric txid rule
    db.execute(
        "INSERT INTO pix_charges (txid, order_id, amount_minor, status, expires_at) "
        "VALUES (%s, %s, %s, 'open', now() + %s * interval '1 second')",
        (txid, order.id, order.total_minor, expires_in_s),
    )
    return txid


def on_pix_received(db, psp, txid: str, end_to_end_id: str, amount_minor: int):
    """Webhook handler. Never trusts the payload alone and never fulfils on name/amount."""
    # Idempotency: the end-to-end id is unique, a replayed webhook is a no-op.
    if db.query_one("SELECT 1 FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,)):
        return "duplicate"

    # Confirm with the PSP API before fulfilling.
    remote = psp.get_charge(txid)
    if remote.status not in ("CONCLUIDA", "ATIVA") or not any(
        p.end_to_end_id == end_to_end_id and p.amount_minor == amount_minor for p in remote.pix
    ):
        return "unconfirmed"

    charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (txid,))
    if charge is None:
        _record_payment(db, end_to_end_id, txid, amount_minor, "exception")
        return "unknown_txid"

    if charge.status != "open" or amount_minor != charge.amount_minor:
        # Expired, already paid, or wrong amount: never a silent credit.
        status = "exception" if EXPIRED_PAYMENT_POLICY == "exception" else "refund_pending"
        _record_payment(db, end_to_end_id, txid, amount_minor, "exception")
        if status == "refund_pending":
            refund(db, psp, end_to_end_id, amount_minor)
        return "refunded_or_exception"

    _record_payment(db, end_to_end_id, txid, amount_minor, "settled")
    db.execute("UPDATE pix_charges SET status = 'paid' WHERE txid = %s", (txid,))
    db.execute("UPDATE orders SET status = 'paid' WHERE id = %s AND status = 'pending'", (charge.order_id,))
    return "paid"


def refund(db, psp, end_to_end_id: str, amount_minor: int) -> None:
    """Devolucao against the original end-to-end id. Full or partial, tracked cumulatively."""
    pay = db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,))
    if pay is None or pay.refunded_minor + amount_minor > pay.amount_minor:
        raise ValueError("refund exceeds the original payment")
    psp.create_devolucao(end_to_end_id, id=uuid.uuid4().hex[:32], amount_minor=amount_minor)
    new_total = pay.refunded_minor + amount_minor
    db.execute(
        "UPDATE pix_payments SET refunded_minor = %s, status = CASE WHEN %s = amount_minor "
        "THEN 'refunded' ELSE status END WHERE end_to_end_id = %s",
        (new_total, new_total, end_to_end_id),
    )


def on_med_claim_opened(db, end_to_end_id: str):
    """The customer disputed this Pix through MED and the order may already be shipped.

    We cannot contest MED the way we contest a card chargeback: it covers fraud and
    operational failure, and the institution may block and return the funds, now or later
    as the balance arrives (up to 90 days). So we (1) record it idempotently, (2) stop
    anything not yet shipped, (3) open a recovery case if shipped, (4) book the exposure.
    """
    pay = db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,))
    if pay is None:
        return "unknown_payment"
    if db.query_one("SELECT 1 FROM pix_disputes WHERE end_to_end_id = %s", (end_to_end_id,)):
        return "duplicate"

    charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (pay.txid,))
    order = db.query_one("SELECT * FROM orders WHERE id = %s", (charge.order_id,))
    shipped = order.shipped_at is not None

    db.execute(
        "INSERT INTO pix_disputes (end_to_end_id, opened_at, status, order_shipped, amount_minor) "
        "VALUES (%s, now(), 'open', %s, %s)",
        (end_to_end_id, shipped, pay.amount_minor),
    )
    db.execute("UPDATE pix_payments SET status = 'disputed' WHERE end_to_end_id = %s", (end_to_end_id,))

    if not shipped:
        db.execute("UPDATE orders SET status = 'disputed', hold_fulfilment = true WHERE id = %s", (order.id,))
        return "held_before_shipping"

    # Already shipped: ask the carrier to intercept/return, and gather evidence for the
    # institution (order, delivery proof, customer contact). Finance books the exposure.
    db.execute("UPDATE orders SET status = 'recovery' WHERE id = %s", (order.id,))
    db.execute(
        "INSERT INTO recovery_cases (order_id, end_to_end_id, kind, amount_minor, status) "
        "VALUES (%s, %s, 'med_shipped', %s, 'open')",
        (order.id, end_to_end_id, pay.amount_minor),
    )
    return "recovery_opened"


def on_med_funds_returned(db, end_to_end_id: str, amount_minor: int):
    """Funds left our account (possibly in several partial returns over up to 90 days)."""
    pay = db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,))
    if pay is None:
        return "unknown_payment"
    new_total = pay.refunded_minor + amount_minor
    db.execute(
        "UPDATE pix_payments SET refunded_minor = %s, status = CASE WHEN %s >= amount_minor "
        "THEN 'clawed_back' ELSE status END WHERE end_to_end_id = %s",
        (new_total, new_total, end_to_end_id),
    )
    if new_total >= pay.amount_minor:
        db.execute("UPDATE pix_disputes SET status = 'funds_returned' WHERE end_to_end_id = %s", (end_to_end_id,))
        # If goods were not recovered, order becomes a loss (ledger entry: expense/receivable
        # per the double-entry ledger); if recovered, close the recovery case instead.
        db.execute(
            "UPDATE orders SET status = CASE WHEN EXISTS (SELECT 1 FROM recovery_cases "
            "WHERE end_to_end_id = %s AND status = 'goods_recovered') THEN 'cancelled' ELSE 'lost' END "
            "WHERE id = (SELECT order_id FROM pix_charges WHERE txid = %s)",
            (end_to_end_id, pay.txid),
        )
    return "recorded"
