"""Wallets."""


class InsufficientFunds(Exception):
    pass


def pay(db, user_id: str, amount: int) -> None:
    """Debit atomically; the balance check and update happen in one statement."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    cur = db.execute(
        "UPDATE wallets SET balance = balance - %s WHERE user_id = %s AND balance >= %s",
        (amount, user_id, amount),
    )
    if getattr(cur, "rowcount", 1) == 0:
        raise InsufficientFunds(user_id)
