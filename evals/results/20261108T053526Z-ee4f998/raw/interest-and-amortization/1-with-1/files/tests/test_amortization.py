import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amortization import (ROUND_HALF_EVEN, ROUND_HALF_UP, Contract, DayCount, money,  # noqa: E402
                          price_installment, price_schedule, sac_schedule, simple_interest)

LOAN = Contract(D("1000.00"), D("0.01"), 12, date(2026, 12, 8))


def test_price_installment_and_totals():
    rows = price_schedule(LOAN)
    assert price_installment(LOAN) == D("88.85")
    assert len(rows) == 12
    assert all(r.installment == D("88.85") for r in rows[:-1])
    assert sum(r.principal for r in rows) == D("1000.00")
    assert rows[-1].balance == D("0")
    assert rows[0].interest == D("10.00")
    assert rows[0].principal == D("78.85")


def test_price_last_installment_absorbs_residual():
    last = price_schedule(LOAN)[-1]
    assert last.installment == last.principal + last.interest
    assert abs(last.installment - D("88.85")) < D("0.15")


def test_due_dates_monthly():
    rows = price_schedule(LOAN)
    assert rows[0].due_date == date(2026, 12, 8)
    assert rows[1].due_date == date(2027, 1, 8)
    assert rows[-1].due_date == date(2027, 11, 8)


def test_due_date_clamps_month_end():
    c = Contract(D("100"), D("0.01"), 3, date(2027, 1, 31))
    assert [r.due_date for r in price_schedule(c)] == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)]


def test_sac():
    rows = sac_schedule(LOAN)
    assert all(r.principal == D("83.33") for r in rows[:-1])
    assert rows[-1].principal == D("83.37")
    assert rows[0].interest == D("10.00")
    assert rows[0].installment == D("93.33")
    assert sum(r.principal for r in rows) == D("1000.00")
    assert rows[-1].balance == D("0")


def test_simple_interest_act365():
    assert simple_interest(D("1000.00"), D("0.12"), 30, DayCount.ACT_365) == D("9.86")


def test_single_period():
    c = Contract(D("1000.00"), D("0.01"), 1)
    (row,) = price_schedule(c)
    assert row.installment == D("1010.00")
    assert row.principal == D("1000.00") and row.balance == D("0")


def test_leap_year_day_counts_differ():
    # 366 days from 2028-01-01 to 2029-01-01 (2028 is a leap year)
    a365 = simple_interest(D("1000.00"), D("0.12"), 366, DayCount.ACT_365)
    a360 = simple_interest(D("1000.00"), D("0.12"), 366, DayCount.ACT_360)
    assert a365 == D("120.33")
    assert a360 == D("122.00")


def test_rounding_policy_visible():
    assert money(D("0.125"), ROUND_HALF_UP) == D("0.13")
    assert money(D("0.125"), ROUND_HALF_EVEN) == D("0.12")
