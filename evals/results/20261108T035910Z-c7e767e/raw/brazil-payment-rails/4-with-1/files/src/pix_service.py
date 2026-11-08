"""Pix as it exists today: one static QR code for the store.

Orders are matched by payer name + amount. Because a static QR carries no txid
and can be paid any number of times for any amount, every received Pix is
recorded by endToEndId and anything that is not an unambiguous match goes to
manual review instead of being silently credited or dropped.
"""

STATIC_QR = "00020126...static..."


def pix_payload_for(order):
    return STATIC_QR


def on_pix_received(db, end_to_end_id: str, payer_name: str, amount_minor: int) -> str:
    """Process a received Pix. Returns the outcome:
    'duplicate' | 'paid' | 'review'.
    """
    # Idempotency: the same endToEndId is processed once (webhook retries).
    if db.query_one("SELECT 1 FROM pix_receipts WHERE end_to_end_id = %s", (end_to_end_id,)):
        return "duplicate"

    matches = db.query_one(
        "SELECT COUNT(*) AS n, MIN(id) AS id FROM orders "
        "WHERE customer_name = %s AND total_minor = %s AND status = 'pending'",
        (payer_name, amount_minor),
    )

    # Exactly one pending order with that name and exact amount -> pay it.
    # Zero (under/overpayment, unknown payer, order already paid = repeat payment)
    # or several (same name, same amount) -> review, never guess.
    if matches and matches.n == 1:
        outcome, order_id = "paid", matches.id
        db.execute("UPDATE orders SET status = 'paid' WHERE id = %s", (order_id,))
    else:
        outcome, order_id = "review", None

    db.execute(
        "INSERT INTO pix_receipts (end_to_end_id, payer_name, amount_minor, order_id, outcome) "
        "VALUES (%s, %s, %s, %s, %s)",
        (end_to_end_id, payer_name, amount_minor, order_id, outcome),
    )
    return outcome
