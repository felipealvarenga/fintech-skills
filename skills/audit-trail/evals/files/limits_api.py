"""Admin endpoint: change a customer's transfer limit."""

def set_transfer_limit(db, customer_id: str, new_limit_minor: int):
    db.execute("UPDATE customers SET transfer_limit = %s WHERE id = %s", (new_limit_minor, customer_id))
    db.commit()
