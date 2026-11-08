"""Admin endpoint: change a customer's transfer limit.

Every change is recorded in the `transfer_limit_audit` table, in the same
transaction as the update, so a limit can never change without an audit row.

Expected table (adapt to your migration tooling):

    CREATE TABLE transfer_limit_audit (
        id               BIGSERIAL PRIMARY KEY,
        customer_id      TEXT        NOT NULL,
        actor_id         TEXT        NOT NULL,  -- authenticated admin making the change
        old_limit_minor  BIGINT,
        new_limit_minor  BIGINT      NOT NULL,
        reason           TEXT,
        changed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
    );
"""


def set_transfer_limit(db, customer_id: str, new_limit_minor: int, actor_id: str, reason: str | None = None):
    if not actor_id:
        raise ValueError("actor_id is required for audited limit changes")

    try:
        # Lock the row so the recorded old value is the one actually replaced.
        row = db.execute(
            "SELECT transfer_limit FROM customers WHERE id = %s FOR UPDATE", (customer_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"customer {customer_id} not found")
        old_limit_minor = row[0]

        db.execute(
            "UPDATE customers SET transfer_limit = %s WHERE id = %s",
            (new_limit_minor, customer_id),
        )
        db.execute(
            "INSERT INTO transfer_limit_audit "
            "(customer_id, actor_id, old_limit_minor, new_limit_minor, reason) "
            "VALUES (%s, %s, %s, %s, %s)",
            (customer_id, actor_id, old_limit_minor, new_limit_minor, reason),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
