"""Admin endpoint: change a customer's transfer limit."""

# Expected schema (add as a migration):
#   CREATE TABLE transfer_limit_audit (
#       id             BIGSERIAL PRIMARY KEY,
#       customer_id    TEXT        NOT NULL,
#       actor_id       TEXT        NOT NULL,   -- admin who made the change
#       old_limit      BIGINT,                 -- minor units; NULL if unset
#       new_limit      BIGINT      NOT NULL,   -- minor units
#       reason         TEXT,
#       changed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
#   );


def set_transfer_limit(db, customer_id: str, new_limit_minor: int, actor_id: str, reason: str | None = None):
    """Update a customer's transfer limit and record an audit entry.

    The update and the audit insert happen in one transaction: if either
    fails, neither is persisted.
    """
    if not actor_id:
        raise ValueError("actor_id is required for audited changes")

    try:
        # Lock the row so the recorded old value is the value actually replaced.
        row = db.execute(
            "SELECT transfer_limit FROM customers WHERE id = %s FOR UPDATE",
            (customer_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"customer {customer_id} not found")
        old_limit = row[0]

        db.execute(
            "UPDATE customers SET transfer_limit = %s WHERE id = %s",
            (new_limit_minor, customer_id),
        )
        db.execute(
            "INSERT INTO transfer_limit_audit "
            "(customer_id, actor_id, old_limit, new_limit, reason) "
            "VALUES (%s, %s, %s, %s, %s)",
            (customer_id, actor_id, old_limit, new_limit_minor, reason),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
