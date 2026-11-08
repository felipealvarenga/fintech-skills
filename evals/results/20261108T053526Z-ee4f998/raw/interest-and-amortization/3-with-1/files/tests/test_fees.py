import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fees import installment_charges, installment_due


def test_on_time_has_no_charges():
    c = installment_charges("100.00", 0)
    assert c.late_interest == Decimal("0.00")
    assert c.fine == Decimal("0.00")
    assert installment_due("100.00", 0) == Decimal("100.00")


def test_late_30_days_separate_lines():
    c = installment_charges("100.00", 30)
    assert c.installment == Decimal("100.00")
    assert c.late_interest == Decimal("1.00")  # 1% a month, 30 days
    assert c.fine == Decimal("2.00")           # 2% once
    assert c.total == Decimal("103.00")


def test_one_day_late_rounds_half_up():
    c = installment_charges("100.00", 1)
    assert c.late_interest == Decimal("0.03")  # 0.0333...
    assert c.fine == Decimal("2.00")
    assert installment_due("100.00", 1) == Decimal("102.03")


def test_custom_rates():
    c = installment_charges("200.00", 15, Decimal("0.10"), Decimal("0.02"))
    assert c.fine == Decimal("20.00")
    assert c.late_interest == Decimal("2.00")
