"""Wallets. Every change is a journal row plus a guarded balance update, in one transaction."""


class InsufficientFunds(Exception):
    pass


def pay(db, user_id: str, amount: int, reference: str) -> None:
    """`reference` is a caller-chosen unique id (e.g. order id); replays are no-ops."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    with db.transaction():
        inserted = db.execute(
            "INSERT INTO wallet_entries (user_id, amount, reference) VALUES (%s, %s, %s) "
            "ON CONFLICT (reference) DO NOTHING",
            (user_id, -amount, reference),
        )
        if getattr(inserted, "rowcount", 1) == 0:
            return  # already applied
        updated = db.execute(
            "UPDATE wallets SET balance = balance - %s WHERE user_id = %s AND balance >= %s",
            (amount, user_id, amount),
        )
        if getattr(updated, "rowcount", 1) == 0:
            raise InsufficientFunds(user_id)  # rolls back the journal row
