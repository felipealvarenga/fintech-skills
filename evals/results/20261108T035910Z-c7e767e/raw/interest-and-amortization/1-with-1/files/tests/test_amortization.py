import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from amortization import (DayCount, LoanContract, Rounding, ScheduleType,  # noqa: E402
                          build_schedule, money, simple_interest)

START = date(2026, 12, 8)


def contract(**kw):
    base = dict(principal=D("1000.00"), periodic_rate=D("0.01"), periods=12, first_due_date=START)
    base.update(kw)
    return LoanContract(**base)


def test_price_12x_1pct():
    rows = build_schedule(contract())
    assert rows[0].installment == D("88.85")
    assert rows[0].interest == D("10.00")
    assert rows[0].principal == D("78.85")
    assert sum(r.principal for r in rows) == D("1000.00")
    assert rows[-1].balance == 0
    assert all(r.installment == D("88.85") for r in rows[:-1])
    assert abs(rows[-1].installment - D("88.85")) < D("0.10")


def test_price_due_dates_monthly():
    rows = build_schedule(contract(first_due_date=date(2026, 1, 31)))
    assert rows[1].due_date == date(2026, 2, 28)
    assert rows[2].due_date == date(2026, 3, 31)


def test_sac():
    rows = build_schedule(contract(schedule_type=ScheduleType.SAC))
    assert all(r.principal == D("83.33") for r in rows[:11])
    assert rows[-1].principal == D("83.37")
    assert rows[0].interest == D("10.00")
    assert rows[0].installment == D("93.33")
    assert sum(r.principal for r in rows) == D("1000.00")
    assert rows[-1].balance == 0


def test_single_period():
    rows = build_schedule(contract(periods=1))
    assert len(rows) == 1
    assert rows[0].installment == D("1010.00")
    assert rows[0].balance == 0


def test_simple_interest_act365():
    assert simple_interest(D("1000.00"), D("0.12"), 30, DayCount.ACT_365) == D("9.86")


def test_leap_year_day_counts_differ():
    # 366 days (2024-01-01 -> 2025-01-01)
    assert simple_interest(D("1000.00"), D("0.12"), 366, DayCount.ACT_365) == D("120.33")
    assert simple_interest(D("1000.00"), D("0.12"), 366, DayCount.ACT_360) == D("122.00")


def test_rounding_policies_differ():
    assert money(D("0.125"), Rounding.HALF_UP) == D("0.13")
    assert money(D("0.125"), Rounding.HALF_EVEN) == D("0.12")
