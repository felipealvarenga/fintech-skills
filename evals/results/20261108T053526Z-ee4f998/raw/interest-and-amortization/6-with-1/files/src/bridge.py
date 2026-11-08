"""Short-term (bridge) loan interest.

Simple interest on a nominal annual rate, with an explicit day-count convention.
Computed in Decimal; rounded once, when the value becomes a posting.
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, localcontext

DAY_COUNT_BASIS = {"ACT/360": 360, "ACT/365": 365}


def interest(
    principal: Decimal | str,
    annual_rate: Decimal | str,
    days: int,
    day_count: str = "ACT/360",
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    """Simple interest = principal * annual_rate * days / basis, rounded to cents.

    annual_rate is a nominal annual rate as a decimal fraction (18% -> "0.18").
    day_count defaults to ACT/360, the convention the previous implementation used;
    pass "ACT/365" if the contract says so.
    """
    if day_count not in DAY_COUNT_BASIS:
        raise ValueError(f"unsupported day count: {day_count}")
    if days < 0:
        raise ValueError("days must be >= 0")
    with localcontext() as ctx:
        ctx.prec = 28
        raw = (
            Decimal(str(principal))
            * Decimal(str(annual_rate))
            * Decimal(days)
            / Decimal(DAY_COUNT_BASIS[day_count])
        )
    return raw.quantize(Decimal("0.01"), rounding=rounding)


def bridge_interest_45d_18pct(principal: Decimal | str, day_count: str = "ACT/360") -> Decimal:
    """Interest for a 45-day bridge loan at 18% a year (nominal, simple)."""
    return interest(principal, "0.18", 45, day_count)
