"""Wallets."""


class InsufficientFunds(Exception):
    pass


def pay(db, user_id: str, amount: int) -> None:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer (cents)")
    # Atomic conditional update: no read-modify-write race, no negative balance.
    cur = db.execute(
        "UPDATE wallets SET balance = balance - %s WHERE user_id = %s AND balance >= %s",
        (amount, user_id, amount),
    )
    if getattr(cur, "rowcount", 1) == 0:
        raise InsufficientFunds(user_id)
