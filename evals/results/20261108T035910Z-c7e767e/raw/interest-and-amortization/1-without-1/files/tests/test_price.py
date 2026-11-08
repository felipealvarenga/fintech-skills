import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from price import price_table  # noqa: E402


def test_loan_1000_1pct_12m():
    rows = price_table("1000.00", "0.01", 12)
    assert len(rows) == 12
    assert rows[0][1] == Decimal("88.85")
    assert rows[0][2] == Decimal("10.00")
    assert rows[0][3] == Decimal("78.85")
    assert rows[-1][4] == Decimal("0")
    assert sum(r[3] for r in rows) == Decimal("1000.00")


def test_payments_constant_except_last_adjustment():
    rows = price_table("1000.00", "0.01", 12)
    assert all(r[1] == Decimal("88.85") for r in rows[:-1])
    assert abs(rows[-1][1] - Decimal("88.85")) < Decimal("0.10")
