"""User wallets, shared by Brazil (BRL) and US (USD) users.

The balance column on the users table is always stored in USD. BRL amounts are
converted to USD on the fly using the rate returned by `rate_provider`.
"""
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Callable

SUPPORTED = {"USD", "BRL"}
CENT = Decimal("0.01")

# Returns how many BRL equal 1 USD (e.g. Decimal("5.40")). Must be set by the
# application at startup (e.g. backed by an FX service or cached rate table).
rate_provider: Callable[[], Decimal] | None = None


def _usd_rate() -> Decimal:
    if rate_provider is None:
        raise RuntimeError("wallet.rate_provider is not configured")
    rate = Decimal(rate_provider())
    if rate <= 0:
        raise ValueError("invalid BRL/USD rate")
    return rate


def to_usd(amount, currency: str) -> Decimal:
    """Convert `amount` in `currency` to USD, rounded to cents."""
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("amount must be positive")
    if currency == "USD":
        usd = amount
    elif currency == "BRL":
        usd = amount / _usd_rate()
    else:
        raise ValueError(f"unsupported currency: {currency}")
    return usd.quantize(CENT, rounding=ROUND_HALF_EVEN)


def from_usd(usd, currency: str) -> Decimal:
    """Convert a USD amount to `currency` for display."""
    usd = Decimal(str(usd))
    if currency == "USD":
        return usd.quantize(CENT)
    if currency == "BRL":
        return (usd * _usd_rate()).quantize(CENT, rounding=ROUND_HALF_EVEN)
    raise ValueError(f"unsupported currency: {currency}")


def pay(db, user_id: str, amount, currency: str = "USD") -> None:
    usd = to_usd(amount, currency)
    db.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (usd, user_id))


def top_up(db, user_id: str, amount, currency: str = "USD") -> None:
    usd = to_usd(amount, currency)
    db.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (usd, user_id))


def get_balance(db, user_id: str, currency: str = "USD") -> Decimal:
    """Return the user's balance in the requested currency."""
    row = db.execute("SELECT balance FROM users WHERE id = %s", (user_id,)).fetchone()
    return from_usd(row[0], currency)
