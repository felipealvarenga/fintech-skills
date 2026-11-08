"""User wallets. Balance is a column on the users table."""

def pay(db, user_id: str, amount: float) -> None:
    db.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, user_id))


def top_up(db, user_id: str, amount: float) -> None:
    db.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
