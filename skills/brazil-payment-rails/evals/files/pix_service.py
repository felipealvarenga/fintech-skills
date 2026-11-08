"""Pix as it exists today: one static QR code for the store."""

STATIC_QR = "00020126...static..."


def pix_payload_for(order):
    return STATIC_QR


def on_pix_received(db, payer_name: str, amount_minor: int):
    order = db.query_one("SELECT * FROM orders WHERE customer_name = %s AND total_minor = %s AND status = 'pending'", (payer_name, amount_minor))
    if order:
        db.execute("UPDATE orders SET status = 'paid' WHERE id = %s", (order.id,))
