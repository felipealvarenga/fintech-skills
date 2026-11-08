import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from schedule import Contract, price_schedule, price_schedule_with_prepayment

C = Contract(principal_minor=100_000, periodic_rate="0.01", periods=12)


def test_price_basic():
    rows = price_schedule(C)
    assert rows[0]["installment_minor"] == 8885
    assert sum(r["principal_minor"] for r in rows) == 100_000
    assert rows[-1]["balance_minor"] == 0


def test_single_period():
    rows = price_schedule(Contract(100_000, "0.01", 1))
    assert len(rows) == 1 and rows[0]["installment_minor"] == 101_000


def test_rounding_policy_visible():
    # 0.5 minor unit of interest: balance 50 at 1% -> HALF_UP 1, HALF_EVEN 0
    up = price_schedule(Contract(50, "0.01", 1, "ROUND_HALF_UP"))
    even = price_schedule(Contract(50, "0.01", 1, "ROUND_HALF_EVEN"))
    assert up[0]["interest_minor"] == 1 and even[0]["interest_minor"] == 0


def test_prepayment_reduce_term():
    rows = price_schedule_with_prepayment(C, 30_000, 4, "reduce_term")
    assert rows[3]["prepayment_minor"] == 30_000
    assert rows[:3] == [dict(r, prepayment_minor=0) for r in price_schedule(C)[:3]]
    assert len(rows) < 12
    assert rows[-1]["balance_minor"] == 0
    assert sum(r["principal_minor"] for r in rows) + 30_000 == 100_000
    assert rows[4]["installment_minor"] == 8885


def test_prepayment_reduce_installment():
    rows = price_schedule_with_prepayment(C, 30_000, 4, "reduce_installment")
    assert len(rows) == 12
    assert rows[4]["installment_minor"] < 8885
    assert rows[-1]["balance_minor"] == 0
    assert sum(r["principal_minor"] for r in rows) + 30_000 == 100_000


def test_prepayment_does_not_mutate_original():
    before = price_schedule(C)
    price_schedule_with_prepayment(C, 30_000, 4, "reduce_term")
    assert price_schedule(C) == before


def test_invalid_mode():
    with pytest.raises(ValueError):
        price_schedule_with_prepayment(C, 30_000, 4, "other")
