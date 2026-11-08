"""Fee schedule."""
# columns: id, product, fee_bps, updated_at
def update_fee(db, product, fee_bps):
    db.execute("UPDATE fees SET fee_bps = %s, updated_at = now() WHERE product = %s", (fee_bps, product))
