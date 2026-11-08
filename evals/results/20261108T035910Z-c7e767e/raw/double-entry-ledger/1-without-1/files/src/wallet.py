"""User wallets. Balance is a NUMERIC(12,2) column on the users table."""
from decimal import Decimal


class InsufficientFunds(Exception):
    pass


def _check_amount(amount: Decimal) -> Decimal:
    amount = Decimal(amount)
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be a positive number")
    return amount


def pay(db, user_id: str, amount: Decimal) -> None:
    """Atomically decrement the balance; fails if funds are insufficient."""
    amount = _check_amount(amount)
    cur = db.execute(
        "UPDATE users SET balance = balance - %s WHERE id = %s AND balance >= %s",
        (amount, user_id, amount),
    )
    if cur.rowcount != 1:
        raise InsufficientFunds(f"user {user_id} not found or balance too low")


def top_up(db, user_id: str, amount: Decimal) -> None:
    amount = _check_amount(amount)
    db.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
