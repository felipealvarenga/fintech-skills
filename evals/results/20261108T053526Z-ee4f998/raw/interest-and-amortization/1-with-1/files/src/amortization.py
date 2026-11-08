"""Loan schedules (Price and SAC) and simple-interest accrual.

Pure functions, Decimal arithmetic, no I/O and no clock. Calculations run at a
high scale; rounding happens only on posted values (installment, interest).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from enum import Enum

CENT = Decimal("0.01")


class DayCount(Enum):
    ACT_365 = 365
    ACT_360 = 360


@dataclass(frozen=True)
class Contract:
    principal: Decimal
    periodic_rate: Decimal  # effective rate per period, e.g. Decimal("0.01") = 1% a month
    periods: int
    first_due_date: date | None = None  # monthly due dates; None leaves due_date empty
    rounding: str = ROUND_HALF_UP


@dataclass(frozen=True)
class Row:
    period: int
    due_date: date | None
    installment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


def money(value: Decimal, rounding: str = ROUND_HALF_UP) -> Decimal:
    return value.quantize(CENT, rounding=rounding)


def _due_date(first: date | None, k: int) -> date | None:
    if first is None:
        return None
    m = first.month - 1 + k
    year, month = first.year + m // 12, m % 12 + 1
    return date(year, month, min(first.day, calendar.monthrange(year, month)[1]))


def _validate(c: Contract) -> None:
    if c.principal <= 0 or c.periods < 1 or c.periodic_rate < 0:
        raise ValueError("invalid contract")


def price_installment(c: Contract) -> Decimal:
    """Constant installment: P*i / (1 - (1+i)^-n), rounded once."""
    _validate(c)
    with localcontext() as ctx:
        ctx.prec = 40
        if c.periodic_rate == 0:
            raw = c.principal / c.periods
        else:
            i = c.periodic_rate
            raw = c.principal * i / (1 - (1 + i) ** -c.periods)
        return money(raw, c.rounding)


def price_schedule(c: Contract) -> list[Row]:
    """Price schedule. The last row pays the remaining balance plus its interest,
    so the residual from rounding is visible there and principal sums exactly."""
    pmt = price_installment(c)
    balance = c.principal
    rows: list[Row] = []
    for k in range(1, c.periods + 1):
        interest = money(balance * c.periodic_rate, c.rounding)
        if k == c.periods:
            principal = balance
        else:
            principal = pmt - interest
        installment = principal + interest
        balance -= principal
        rows.append(Row(k, _due_date(c.first_due_date, k - 1), installment, interest, principal, balance))
    return rows


def sac_schedule(c: Contract) -> list[Row]:
    """Constant amortization; last row pays the remainder."""
    _validate(c)
    amort = money(c.principal / c.periods, c.rounding)
    balance = c.principal
    rows: list[Row] = []
    for k in range(1, c.periods + 1):
        interest = money(balance * c.periodic_rate, c.rounding)
        principal = balance if k == c.periods else amort
        balance -= principal
        rows.append(Row(k, _due_date(c.first_due_date, k - 1), principal + interest, interest, principal, balance))
    return rows


def simple_interest(principal: Decimal, annual_rate: Decimal, days: int,
                    day_count: DayCount, rounding: str = ROUND_HALF_UP) -> Decimal:
    """Simple interest, rounded once at posting."""
    with localcontext() as ctx:
        ctx.prec = 40
        return money(principal * annual_rate * days / day_count.value, rounding)


__all__ = ["Contract", "DayCount", "Row", "ROUND_HALF_EVEN", "ROUND_HALF_UP", "money",
           "price_installment", "price_schedule", "sac_schedule", "simple_interest"]
