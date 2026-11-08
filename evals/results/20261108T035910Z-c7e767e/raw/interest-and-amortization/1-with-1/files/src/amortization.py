"""Loan schedules: Price (constant installment) and SAC (constant amortization).

Pure functions, no I/O, no clock. Calculation runs in Decimal at 28 digits;
values are rounded only when they become postings (installment, interest).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from enum import Enum

CENT = Decimal("0.01")


class Rounding(Enum):
    HALF_UP = ROUND_HALF_UP
    HALF_EVEN = ROUND_HALF_EVEN


class ScheduleType(Enum):
    PRICE = "PRICE"
    SAC = "SAC"


class DayCount(Enum):
    ACT_365 = 365
    ACT_360 = 360


@dataclass(frozen=True)
class LoanContract:
    principal: Decimal
    periodic_rate: Decimal  # effective monthly rate as a decimal, e.g. 0.01 = 1% a month
    periods: int
    first_due_date: date
    schedule_type: ScheduleType = ScheduleType.PRICE
    rounding: Rounding = Rounding.HALF_UP
    # Rate kind: periodic_rate is the *effective monthly* rate, applied once per month.
    # Monthly periods are not day-counted; day count only applies to simple_interest().


@dataclass(frozen=True)
class Row:
    period: int
    due_date: date
    installment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


def money(value: Decimal, rounding: Rounding = Rounding.HALF_UP) -> Decimal:
    return value.quantize(CENT, rounding=rounding.value)


def add_months(start: date, months: int) -> date:
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def price_installment(principal: Decimal, rate: Decimal, n: int, rounding: Rounding) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        if rate == 0:
            return money(principal / n, rounding)
        pmt = principal * rate / (1 - (1 + rate) ** -n)
    return money(pmt, rounding)


def build_schedule(c: LoanContract) -> list[Row]:
    if c.principal <= 0 or c.periods < 1 or c.periodic_rate < 0:
        raise ValueError("invalid contract")
    rows: list[Row] = []
    balance = c.principal
    if c.schedule_type is ScheduleType.PRICE:
        pmt = price_installment(c.principal, c.periodic_rate, c.periods, c.rounding)
        amort = None
    else:
        pmt = None
        amort = money(c.principal / c.periods, c.rounding)

    for k in range(1, c.periods + 1):
        interest = money(balance * c.periodic_rate, c.rounding)
        if k == c.periods:  # last one absorbs the rounding residual
            principal = balance
        elif pmt is not None:
            principal = pmt - interest
        else:
            principal = amort
        balance -= principal
        rows.append(Row(k, add_months(c.first_due_date, k - 1),
                        principal + interest, interest, principal, balance))
    return rows


def simple_interest(principal: Decimal, annual_rate: Decimal, days: int,
                    day_count: DayCount, rounding: Rounding = Rounding.HALF_UP) -> Decimal:
    return money(principal * annual_rate * days / day_count.value, rounding)


def format_brl(v: Decimal) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def render(rows: list[Row]) -> str:
    head = f"{'Parc':>4} {'Vencimento':>10} {'Prestação':>11} {'Juros':>9} {'Amortização':>12} {'Saldo':>10}"
    lines = [head]
    for r in rows:
        lines.append(f"{r.period:>4} {r.due_date.isoformat():>10} {format_brl(r.installment):>11} "
                     f"{format_brl(r.interest):>9} {format_brl(r.principal):>12} {format_brl(r.balance):>10}")
    lines.append(f"{'Total':>15} {format_brl(sum(r.installment for r in rows)):>11} "
                 f"{format_brl(sum(r.interest for r in rows)):>9} "
                 f"{format_brl(sum(r.principal for r in rows)):>12}")
    return "\n".join(lines)


if __name__ == "__main__":
    contract = LoanContract(Decimal("1000.00"), Decimal("0.01"), 12, date(2026, 12, 8))
    print(render(build_schedule(contract)))
