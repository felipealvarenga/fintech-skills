import sys
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from bridge import bridge_interest_45d_18pct, interest  # noqa: E402


def test_45_days_18pct_act360():
    assert bridge_interest_45d_18pct("1000.00") == Decimal("22.50")


def test_45_days_18pct_act365():
    assert bridge_interest_45d_18pct("1000.00", "ACT/365") == Decimal("22.19")


def test_simple_interest_reference():
    assert interest("1000.00", "0.12", 30, "ACT/365") == Decimal("9.86")


def test_zero_days():
    assert interest("1000.00", "0.18", 0) == Decimal("0.00")


def test_day_counts_differ_both_asserted():
    assert interest("100000.00", "0.18", 366, "ACT/360") == Decimal("18300.00")
    assert interest("100000.00", "0.18", 366, "ACT/365") == Decimal("18049.32")


def test_rounding_policy_visible():
    # 0.10 * 0.15 * 1 / 360 * ... pick a value landing exactly on a half cent
    # 1000 * 0.18 * 1 / 360 = 0.50 -> use 10.00*0.18*1/360 = 0.005
    assert interest("10.00", "0.18", 1, rounding=ROUND_HALF_UP) == Decimal("0.01")
    assert interest("10.00", "0.18", 1, rounding=ROUND_HALF_EVEN) == Decimal("0.00")


def test_invalid_day_count():
    with pytest.raises(ValueError):
        interest("1000", "0.18", 45, "30/360")
