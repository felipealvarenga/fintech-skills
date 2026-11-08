"""Wallets."""


def pay(db, user_id: str, amount: int) -> None:
    db.execute("UPDATE wallets SET balance = balance - %s WHERE user_id = %s", (amount, user_id))
