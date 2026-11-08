"""Customer credit limits."""
def set_limit(db, customer_id, new_limit_minor):
    db.execute("UPDATE customers SET credit_limit = %s WHERE id = %s", (new_limit_minor, customer_id))
