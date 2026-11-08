import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from price import price_table


@pytest.fixture
def rows():
    return price_table(Decimal("1000.00"), Decimal("0.01"), 12)


def test_length_and_final_balance(rows):
    assert len(rows) == 12
    assert rows[-1].balance == Decimal("0.00")


def test_payment_is_88_85(rows):
    assert rows[0].payment == Decimal("88.85")


def test_first_interest(rows):
    assert rows[0].interest == Decimal("10.00")


def test_amortization_sums_to_principal(rows):
    assert sum(r.amortization for r in rows) == Decimal("1000.00")


def test_row_consistency(rows):
    for r in rows:
        assert r.payment == r.interest + r.amortization


def test_invalid_input():
    with pytest.raises(ValueError):
        price_table(Decimal("0"), Decimal("0.01"), 12)
