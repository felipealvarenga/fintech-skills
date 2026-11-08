import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schedule_float import price_table


def test_final_balance_is_zero():
    rows = price_table(1000.00, 0.01, 12)
    assert rows[-1]["balance"] == 0


def test_principal_parts_sum_to_principal():
    rows = price_table(1000.00, 0.01, 12)
    assert round(sum(r["amort"] for r in rows), 2) == 1000.00


def test_long_term_ends_at_zero():
    rows = price_table(25000.00, 0.035, 60)
    assert rows[-1]["balance"] == 0


def test_single_period():
    rows = price_table(1000.00, 0.01, 1)
    assert rows[0]["pmt"] == 1010.00
    assert rows[0]["balance"] == 0
