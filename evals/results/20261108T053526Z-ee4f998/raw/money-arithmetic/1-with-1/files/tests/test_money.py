import os
import random
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from money import Money, allocate, apply_rate, convert, from_minor, to_minor  # noqa: E402
from billing import ShareStore, split_100_brl_50_30_20, split_invoice  # noqa: E402


@pytest.mark.parametrize("ccy", ["JPY", "USD", "BRL", "KWD"])
def test_round_trip(ccy):
    for x in [0, 1, 5, 999, 123456, -1234]:
        assert to_minor(from_minor(x, ccy), ccy) == x


def test_parse_refuses_too_many_decimals():
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")
    with pytest.raises(ValueError):
        to_minor("1.5", "JPY")


def test_unknown_currency_refused():
    with pytest.raises(ValueError):
        to_minor("1.00", "XXX")
    with pytest.raises(ValueError):
        Money(100, "XXX")


def test_parse_refuses_nan_and_float():
    with pytest.raises(ValueError):
        to_minor("NaN", "USD")
    with pytest.raises(TypeError):
        to_minor(12.34, "USD")


def test_allocation_property():
    rng = random.Random(1)
    for _ in range(500):
        amount = rng.randint(-100000, 100000)
        ratios = [rng.randint(0, 10) for _ in range(rng.randint(1, 6))]
        if sum(ratios) == 0:
            continue
        parts = allocate(amount, ratios)
        assert sum(parts) == amount
        for p, r in zip(parts, ratios):
            assert abs(p - amount * r / sum(ratios)) < 1
            if r == 0:
                assert p == 0


def test_allocation_thirds():
    assert allocate(10000, [1, 1, 1]) == [3334, 3333, 3333]


def test_mixed_currency_add_raises():
    with pytest.raises(ValueError):
        Money(100, "USD") + Money(100, "BRL")


def test_rate_policy_visible():
    assert apply_rate(1000, "0.0325", ROUND_HALF_EVEN) == 32
    assert apply_rate(1000, "0.0325", ROUND_HALF_UP) == 33


def test_rate_refuses_float():
    with pytest.raises(TypeError):
        apply_rate(1000, 0.0325)


def test_conversion_target_exponent():
    assert convert(1000, "USD", "JPY", "150.5") == 1505


def test_invoice_50_30_20():
    store = ShareStore()
    shares = split_100_brl_50_30_20(store)
    assert [s.amount_minor for s in shares] == [5000, 3000, 2000]
    assert all(s.currency == "BRL" for s in shares)
    assert store.shares == shares


def test_invoice_split_keeps_sum_on_awkward_total():
    store = ShareStore()
    shares = split_invoice("X", Money(10001, "BRL"), {"A": "50", "B": "30", "C": "20"}, store)
    assert sum(s.amount_minor for s in shares) == 10001
