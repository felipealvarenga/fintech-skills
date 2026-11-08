"""Fee schedule service."""

def update_fee(db, fee_id: str, bps: int, updated_by: str):
    db.execute(
        "UPDATE fees SET bps = %s, updated_by = %s, updated_at = now() WHERE id = %s",
        (bps, updated_by, fee_id),
    )
