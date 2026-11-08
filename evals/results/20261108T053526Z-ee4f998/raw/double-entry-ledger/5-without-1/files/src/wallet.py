"""User wallets. Balance is a column on the users table, always stored in USD.

Amounts in other currencies (currently BRL) are converted to USD on the fly
using a caller-supplied rate provider.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

SUPPORTED = {"USD", "BRL"}
CENT = Decimal("0.01")

# Returns how many BRL one USD buys, e.g. Decimal("5.40").
RateProvider = Callable[[], Decimal]


def _d(amount) -> Decimal:
    # str() avoids binary-float artifacts when callers pass floats.
    return Decimal(str(amount))


def to_usd(amount, currency: str, usd_brl: RateProvider) -> Decimal:
    currency = currency.upper()
    if currency not in SUPPORTED:
        raise ValueError(f"unsupported currency: {currency}")
    value = _d(amount)
    if value <= 0:
        raise ValueError("amount must be positive")
    if currency == "BRL":
        rate = _d(usd_brl())
        if rate <= 0:
            raise ValueError("invalid exchange rate")
        value = value / rate
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def from_usd(amount_usd, currency: str, usd_brl: RateProvider) -> Decimal:
    """Convert a stored USD balance for display in the user's currency."""
    currency = currency.upper()
    if currency not in SUPPORTED:
        raise ValueError(f"unsupported currency: {currency}")
    value = _d(amount_usd)
    if currency == "BRL":
        value = value * _d(usd_brl())
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def pay(db, user_id: str, amount, currency: str = "USD",
        usd_brl: RateProvider = None) -> None:
    usd = to_usd(amount, currency, usd_brl)
    cur = db.execute(
        "UPDATE users SET balance = balance - %s WHERE id = %s AND balance >= %s",
        (usd, user_id, usd),
    )
    if getattr(cur, "rowcount", 1) == 0:
        raise ValueError("insufficient funds or unknown user")


def top_up(db, user_id: str, amount, currency: str = "USD",
           usd_brl: RateProvider = None) -> None:
    usd = to_usd(amount, currency, usd_brl)
    db.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (usd, user_id))
