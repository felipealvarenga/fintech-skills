"""Fee schedule service."""

def update_fee(db, fee_id: str, bps: int):
    db.execute("UPDATE fees SET bps = %s, updated_at = now() WHERE id = %s", (bps, fee_id))
