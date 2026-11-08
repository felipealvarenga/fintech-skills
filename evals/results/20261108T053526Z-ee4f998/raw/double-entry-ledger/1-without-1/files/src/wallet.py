"""User wallets. Balance is a column on the users table (NUMERIC(12, 2))."""
from decimal import Decimal


class InsufficientFunds(Exception):
    pass


def _check_amount(amount: Decimal) -> None:
    if not isinstance(amount, Decimal):
        raise TypeError("amount must be a Decimal, not float")
    if amount <= 0:
        raise ValueError("amount must be positive")


def pay(db, user_id: str, amount: Decimal) -> None:
    """Atomically decrement the balance; raises InsufficientFunds if too low."""
    _check_amount(amount)
    cur = db.execute(
        "UPDATE users SET balance = balance - %s WHERE id = %s AND balance >= %s",
        (amount, user_id, amount),
    )
    if cur.rowcount != 1:
        raise InsufficientFunds(f"user {user_id} not found or balance too low")


def top_up(db, user_id: str, amount: Decimal) -> None:
    _check_amount(amount)
    db.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
