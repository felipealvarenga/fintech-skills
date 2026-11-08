"""Tests for src/money_module.py.

Vectors are hand-computed (independent of the code under test) and must be
reviewed by a person; changing one needs a reason in the PR.
"""
import os
import random
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from money_module import EXPONENTS, allocate, apply_rate, to_minor  # noqa: E402

SEED = 20261108
CASES = 500


# ---------------------------------------------------------------- to_minor
@pytest.mark.parametrize(
    "amount,currency,expected",
    [
        ("0", "USD", 0),
        ("0.01", "USD", 1),
        ("10.50", "USD", 1050),
        ("10", "USD", 1000),
        ("-5.25", "BRL", -525),
        ("1234567890.99", "USD", 123456789099),
        ("10", "JPY", 10),
        ("0", "JPY", 0),
        ("1.234", "BHD", 1234),
        ("0.001", "BHD", 1),
        ("-0.001", "BHD", -1),
        ("1.5", "BHD", 1500),
    ],
)
def test_to_minor_vectors(amount, currency, expected):
    result = to_minor(amount, currency)
    assert result == expected
    assert type(result) is int


def test_to_minor_unknown_currency_raises():
    with pytest.raises(KeyError):
        to_minor("1.00", "XXX")


@pytest.mark.xfail(strict=True, reason="BUG: to_minor silently truncates sub-minor "
                   "precision (1.005 USD -> 100). Should raise or round explicitly.")
def test_to_minor_rejects_sub_minor_precision():
    with pytest.raises(ValueError):
        to_minor("1.005", "USD")


@pytest.mark.xfail(strict=True, reason="BUG: JPY 10.5 silently becomes 10.")
def test_to_minor_rejects_fraction_in_zero_decimal_currency():
    with pytest.raises(ValueError):
        to_minor("10.5", "JPY")


def test_to_minor_round_trip_property():
    rng = random.Random(SEED)
    for _ in range(CASES):
        cur = rng.choice(list(EXPONENTS))
        minor = rng.randint(-10**12, 10**12)
        text = str(Decimal(minor).scaleb(-EXPONENTS[cur]))
        # str() may use exponent notation for tiny values; Decimal accepts it
        assert to_minor(text, cur) == minor


# ---------------------------------------------------------------- allocate
@pytest.mark.parametrize(
    "amount,ratios,expected",
    [
        (100, [1, 1, 1], [34, 33, 33]),
        (5, [1, 1], [3, 2]),
        (100, [50, 50], [50, 50]),
        (0, [1, 2, 3], [0, 0, 0]),
        (1, [1, 1, 1], [1, 0, 0]),
        (10, [1], [10]),
        (100, [70, 20, 10], [70, 20, 10]),
        (101, [70, 20, 10], [71, 20, 10]),
        (10, [1, 0, 1], [5, 0, 5]),
        (7, [1, 2], [2, 5]),       # 2.33 / 4.67 -> largest remainder goes to 2nd
        (-100, [1, 1, 1], [-33, -33, -34]),
    ],
)
def test_allocate_vectors(amount, ratios, expected):
    assert allocate(amount, ratios) == expected


def test_allocate_sum_preserved_property():
    rng = random.Random(SEED)
    for _ in range(CASES):
        amount = rng.randint(-10**12, 10**12)
        ratios = [rng.randint(0, 1000) for _ in range(rng.randint(1, 12))]
        if sum(ratios) == 0:
            ratios[0] = 1
        out = allocate(amount, ratios)
        assert len(out) == len(ratios)
        assert sum(out) == amount, (amount, ratios, out)
        assert all(type(x) is int for x in out)


def test_allocate_fairness_property():
    """Each share is within 1 minor unit of the exact proportional share,
    and zero ratios receive nothing (for non-negative amounts)."""
    rng = random.Random(SEED + 1)
    for _ in range(CASES):
        amount = rng.randint(0, 10**9)
        ratios = [rng.randint(0, 100) for _ in range(rng.randint(1, 10))]
        if sum(ratios) == 0:
            ratios[0] = 1
        total = sum(ratios)
        out = allocate(amount, ratios)
        for share, r in zip(out, ratios):
            exact = Decimal(amount * r) / total
            assert abs(Decimal(share) - exact) < 1
            if r == 0:
                assert share == 0


def test_allocate_zero_total_raises():
    with pytest.raises(ZeroDivisionError):
        allocate(100, [0, 0])


def test_allocate_empty_ratios_raises():
    with pytest.raises(ZeroDivisionError):
        allocate(100, [])


# -------------------------------------------------------------- apply_rate
@pytest.mark.parametrize(
    "amount,rate,expected",
    [
        (100, "0.1", 10),
        (5, "0.5", 2),      # 2.5 -> 2 (half-even)
        (15, "0.5", 8),     # 7.5 -> 8
        (25, "0.1", 2),     # 2.5 -> 2
        (35, "0.1", 4),     # 3.5 -> 4
        (-25, "0.1", -2),   # -2.5 -> -2
        (-35, "0.1", -4),
        (26, "0.1", 3),     # 2.6 -> 3
        (24, "0.1", 2),     # 2.4 -> 2
        (0, "5.25", 0),
        (1000, "0", 0),
        (1000, "1", 1000),
        (1000, "1.0825", 1082),   # 1082.5 -> 1082 (even)
        (10000, "0.0825", 825),
        (123456789, "5.5", 679012340),  # 679012339.5 -> 679012340 (even)
    ],
)
def test_apply_rate_vectors(amount, rate, expected):
    assert apply_rate(amount, rate) == expected
    assert type(apply_rate(amount, rate)) is int


def test_apply_rate_not_half_up():
    # Guards against a rounding-mode change: half-up would give 3, half-even 2.
    assert apply_rate(25, "0.1") == 2
    # ...and half-down/truncation would give 2 here, half-even gives 4.
    assert apply_rate(35, "0.1") == 4


def test_apply_rate_error_bounded_property():
    rng = random.Random(SEED + 2)
    for _ in range(CASES):
        amount = rng.randint(-10**12, 10**12)
        rate = f"{rng.randint(0, 10**6)}e-{rng.randint(0, 6)}"
        out = apply_rate(amount, rate)
        exact = Decimal(amount) * Decimal(rate)
        assert abs(Decimal(out) - exact) <= Decimal("0.5")
        assert type(out) is int


def test_apply_rate_invalid_rate_raises():
    with pytest.raises(Exception):
        apply_rate(100, "abc")
