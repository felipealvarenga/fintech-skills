"""Short-term loan interest.

Rate kind: nominal annual rate, simple interest (no compounding).
Day count: ACT/360 by default (the existing behaviour); ACT/365 is selectable.
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext

DAY_BASIS = {"ACT/360": 360, "ACT/365": 365}

BRIDGE_DAYS = 45
BRIDGE_ANNUAL_RATE = Decimal("0.18")


def interest(principal, annual_rate, days: int, day_count: str = "ACT/360") -> Decimal:
    """Simple interest, computed at high precision and rounded once (HALF_UP, 2 places)."""
    basis = DAY_BASIS[day_count]
    with localcontext() as ctx:
        ctx.prec = 28
        raw = Decimal(str(principal)) * Decimal(str(annual_rate)) * days / basis
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def bridge_interest(principal, day_count: str = "ACT/360") -> Decimal:
    """Interest for a 45-day bridge loan at 18% a year."""
    return interest(principal, BRIDGE_ANNUAL_RATE, BRIDGE_DAYS, day_count)
