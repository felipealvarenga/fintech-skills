"""Pix: dynamic charges keyed by txid, payments keyed by endToEndId, MED claims.

Assumed tables (migration needed):
  pix_charges(txid PK, order_id, amount_minor, status, payload)
      status: open | paid | expired
  pix_payments(end_to_end_id PK, txid, amount_minor, returned_minor DEFAULT 0,
               status, received_at)
      status: settled | under_med_claim | partially_returned | returned
  med_claims(claim_id PK, end_to_end_id, order_id, opened_at, status, amount_minor)
      status: open | defended | accepted | closed
  orders gains: fulfillment_status, payment_risk ('none'|'med_claim'|'clawed_back')

MED covers fraud and operational failure, not buyer's remorse. A received Pix
can be clawed back (payer claim up to 80 days after the Pix under MED 2.0; the
institution may return funds over 90 days as the balance allows). Shipping
therefore must not be treated as "money is final".
"""


def create_charge(db, order, psp):
    """Dynamic charge with our own txid, so the amount and order are bound."""
    txid = psp.new_txid()
    payload = psp.create_immediate_charge(txid, order.total_minor, expires_in=3600)
    db.execute(
        "INSERT INTO pix_charges (txid, order_id, amount_minor, status, payload) "
        "VALUES (%s, %s, %s, 'open', %s)",
        (txid, order.id, order.total_minor, payload),
    )
    return payload


def on_pix_received(db, psp, txid: str, end_to_end_id: str, amount_minor: int):
    """Webhook handler. Idempotent on end_to_end_id; confirms with the PSP first."""
    if db.query_one("SELECT 1 FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,)):
        return  # duplicate webhook

    charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (txid,))
    confirmed = psp.get_charge(txid)  # confirm through the API, not the webhook alone
    if not charge or confirmed.status != "paid" or confirmed.amount_minor != amount_minor:
        _send_to_exception_queue(db, txid, end_to_end_id, amount_minor)
        return

    db.execute(
        "INSERT INTO pix_payments (end_to_end_id, txid, amount_minor, status, received_at) "
        "VALUES (%s, %s, %s, 'settled', now())",
        (end_to_end_id, txid, amount_minor),
    )
    if charge.status == "expired":
        # Paid after expiry: policy decision, default is refund via devolucao.
        psp.refund(end_to_end_id, amount_minor)
        return
    db.execute("UPDATE pix_charges SET status = 'paid' WHERE txid = %s", (txid,))
    db.execute("UPDATE orders SET status = 'paid' WHERE id = %s", (charge.order_id,))


def on_med_claim_opened(db, claim_id: str, end_to_end_id: str, amount_minor: int):
    """Payer opened a MED claim. Order may already be shipped."""
    payment = db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,))
    if not payment:
        _send_to_exception_queue(db, None, end_to_end_id, amount_minor)
        return
    if db.query_one("SELECT 1 FROM med_claims WHERE claim_id = %s", (claim_id,)):
        return  # idempotent
    charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (payment.txid,))

    db.execute(
        "INSERT INTO med_claims (claim_id, end_to_end_id, order_id, opened_at, status, amount_minor) "
        "VALUES (%s, %s, %s, now(), 'open', %s)",
        (claim_id, end_to_end_id, charge.order_id, amount_minor),
    )
    db.execute("UPDATE pix_payments SET status = 'under_med_claim' WHERE end_to_end_id = %s", (end_to_end_id,))
    # Flag, don't un-pay: the order stays shipped, but gets a risk marker so that
    # nothing further ships (other orders from the same customer/payer too).
    db.execute("UPDATE orders SET payment_risk = 'med_claim' WHERE id = %s", (charge.order_id,))
    _open_case_for_ops(db, claim_id, charge.order_id)  # evidence: tracking, delivery proof, customer data


def on_pix_returned(db, end_to_end_id: str, returned_minor: int):
    """Funds went back to the payer (MED may return in several parts over 90 days).

    Applies only the new amount; never exceeds the original payment.
    """
    payment = db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,))
    if not payment:
        _send_to_exception_queue(db, None, end_to_end_id, returned_minor)
        return
    total = min(payment.returned_minor + returned_minor, payment.amount_minor)
    status = "returned" if total == payment.amount_minor else "partially_returned"
    db.execute(
        "UPDATE pix_payments SET returned_minor = %s, status = %s WHERE end_to_end_id = %s",
        (total, status, end_to_end_id),
    )
    if status == "returned":
        charge = db.query_one("SELECT * FROM pix_charges WHERE txid = %s", (payment.txid,))
        db.execute("UPDATE orders SET payment_risk = 'clawed_back' WHERE id = %s", (charge.order_id,))
        # Ledger: record the loss / receivable from customer; don't delete the sale.
        # Shipped goods are recovered outside Pix (carrier return, collections, fraud report).


def _send_to_exception_queue(db, txid, end_to_end_id, amount_minor):
    db.execute(
        "INSERT INTO pix_exceptions (txid, end_to_end_id, amount_minor) VALUES (%s, %s, %s)",
        (txid, end_to_end_id, amount_minor),
    )


def _open_case_for_ops(db, claim_id, order_id):
    db.execute("INSERT INTO ops_cases (kind, ref, order_id) VALUES ('med_claim', %s, %s)", (claim_id, order_id))
