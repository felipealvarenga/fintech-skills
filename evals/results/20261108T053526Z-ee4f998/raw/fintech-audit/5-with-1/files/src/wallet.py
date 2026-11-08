"""Wallets. The balance is derived from append-only entries, never updated in place.

Assumed schema: wallet_entries(id, user_id, amount, ref UNIQUE, created_at), amount in
minor units, negative for debits.
"""


class InsufficientFunds(Exception):
    pass


def balance(db, user_id: str) -> int:
    row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM wallet_entries WHERE user_id = %s", (user_id,)
    ).fetchone()
    return int(row[0])


def pay(db, user_id: str, amount: int, ref: str) -> None:
    """Debit `amount`; `ref` is the caller's idempotency key (unique index, first writer wins)."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (user_id,))
    if balance(db, user_id) < amount:
        raise InsufficientFunds(user_id)
    db.execute(
        "INSERT INTO wallet_entries (user_id, amount, ref) VALUES (%s, %s, %s) "
        "ON CONFLICT (ref) DO NOTHING",
        (user_id, -amount, ref),
    )
