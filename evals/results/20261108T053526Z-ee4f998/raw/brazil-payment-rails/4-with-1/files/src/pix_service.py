"""Pix as it exists today: one static QR code for the store.

Orders are matched by payer name + exact amount. Because a static QR can be
paid any number of times for any amount, every received Pix is recorded by
endToEndId and anything that is not an unambiguous exact match goes to the
pix_exceptions queue (refund / manual review) instead of being credited.
"""

STATIC_QR = "00020126...static..."


def pix_payload_for(order):
    return STATIC_QR


def on_pix_received(db, payer_name: str, amount_minor: int, end_to_end_id: str) -> str:
    """Returns 'paid', 'duplicate', or an exception reason."""
    # Webhooks are redelivered: process each endToEndId once.
    if db.query_one("SELECT * FROM pix_payments WHERE end_to_end_id = %s", (end_to_end_id,)):
        return "duplicate"
    db.execute(
        "INSERT INTO pix_payments (end_to_end_id, payer_name, amount_minor, order_id) VALUES (%s, %s, %s, NULL)",
        (end_to_end_id, payer_name, amount_minor),
    )

    exact = db.query_all(
        "SELECT * FROM orders WHERE customer_name = %s AND total_minor = %s AND status = 'pending'",
        (payer_name, amount_minor),
    )
    if len(exact) == 1:
        order = exact[0]
        db.execute("UPDATE orders SET status = 'paid' WHERE id = %s AND status = 'pending'", (order.id,))
        db.execute("UPDATE pix_payments SET order_id = %s WHERE end_to_end_id = %s", (order.id, end_to_end_id))
        return "paid"

    if len(exact) > 1:
        reason = "ambiguous_match"
    elif db.query_all(
        "SELECT * FROM orders WHERE customer_name = %s AND total_minor = %s AND status = 'paid'",
        (payer_name, amount_minor),
    ):
        reason = "repeat_payment"
    elif db.query_all(
        "SELECT * FROM orders WHERE customer_name = %s AND status = 'pending'", (payer_name,)
    ):
        reason = "amount_mismatch"  # over or under payment
    else:
        reason = "unmatched"
    db.execute(
        "INSERT INTO pix_exceptions (end_to_end_id, reason) VALUES (%s, %s)", (end_to_end_id, reason)
    )
    return reason
