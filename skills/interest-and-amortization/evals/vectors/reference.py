"""Reference implementation for the interest-and-amortization vectors.

Amounts are integers in minor units. Rates are decimal strings. Rounding happens once per posted
value with the named policy, and the last installment absorbs the residual.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext

PREC = 40


def _q(value: Decimal, rounding: str) -> int:
    return int(value.quantize(Decimal(1), rounding=rounding))


def price_schedule(principal: int, periodic_rate: str, periods: int,
                   rounding: str = ROUND_HALF_UP) -> list[dict]:
    if principal <= 0 or periods <= 0:
        raise ValueError("principal and periods must be positive")
    with localcontext() as ctx:
        ctx.prec = PREC
        i = Decimal(periodic_rate)
        P = Decimal(principal)
        if i == 0:
            pmt_exact = P / periods
        else:
            pmt_exact = P * i / (1 - (1 + i) ** (-periods))
        pmt = _q(pmt_exact, rounding)
        rows = []
        balance = principal
        for k in range(1, periods + 1):
            interest = _q(Decimal(balance) * i, rounding)
            if k < periods:
                principal_part = pmt - interest
                installment = pmt
            else:
                principal_part = balance
                installment = principal_part + interest
            balance -= principal_part
            rows.append({"period": k, "installment": installment, "interest": interest,
                         "principal": principal_part, "balance": balance})
        return rows


def sac_schedule(principal: int, periodic_rate: str, periods: int,
                 rounding: str = ROUND_HALF_UP) -> list[dict]:
    if principal <= 0 or periods <= 0:
        raise ValueError("principal and periods must be positive")
    with localcontext() as ctx:
        ctx.prec = PREC
        i = Decimal(periodic_rate)
        amort = _q(Decimal(principal) / periods, rounding)
        rows = []
        balance = principal
        for k in range(1, periods + 1):
            interest = _q(Decimal(balance) * i, rounding)
            principal_part = amort if k < periods else balance
            balance -= principal_part
            rows.append({"period": k, "installment": principal_part + interest,
                         "interest": interest, "principal": principal_part, "balance": balance})
        return rows


def simple_interest(principal: int, annual_rate: str, days: int, basis: int = 365,
                    rounding: str = ROUND_HALF_UP) -> int:
    with localcontext() as ctx:
        ctx.prec = PREC
        return _q(Decimal(principal) * Decimal(annual_rate) * days / basis, rounding)


def effective_to_periodic(effective_annual_rate: str, periods_per_year: int = 12) -> Decimal:
    """(1 + r)^(1/n) - 1 at 12 decimal places."""
    with localcontext() as ctx:
        ctx.prec = PREC
        r = Decimal(effective_annual_rate)
        periodic = (1 + r) ** (Decimal(1) / periods_per_year) - 1
        return periodic.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
