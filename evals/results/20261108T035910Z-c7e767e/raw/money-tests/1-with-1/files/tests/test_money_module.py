"""Tests for src/money_module.py.

Vectors are hand-computed (not produced by the code under test) and must be
reviewed by a person; changing one needs a stated reason in the PR.
Property tests use a fixed seed (derandomize) and 300 cases.
"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from money_module import EXPONENTS, allocate, apply_rate, to_minor  # noqa: E402

PROP = settings(max_examples=300, derandomize=True, deadline=None)

# ---------------------------------------------------------------- vectors

TO_MINOR_VECTORS = [
    ("10.25", "USD", 1025),
    ("0", "USD", 0),
    ("0.01", "USD", 1),
    ("-1.23", "BRL", -123),
    ("100", "JPY", 100),
    ("1.005", "BHD", 1005),
    ("0.001", "BHD", 1),
    ("12345678901234.56", "USD", 1234567890123456),  # beyond float precision
]


@pytest.mark.parametrize("amount,cur,expected", TO_MINOR_VECTORS)
def test_to_minor_vectors(amount, cur, expected):
    result = to_minor(amount, cur)
    assert result == expected
    assert type(result) is int


ALLOCATE_VECTORS = [
    (100, [1, 1, 1], [34, 33, 33]),
    (5, [1, 1], [3, 2]),
    (1, [1, 1, 1], [1, 0, 0]),
    (0, [1, 2], [0, 0]),
    (10, [0, 1], [0, 10]),
    (101, [70, 30], [71, 30]),
    (100, [50, 50], [50, 50]),
    (-100, [1, 1, 1], [-33, -33, -34]),  # floor semantics; sum preserved
    (7, [5], [7]),
]


@pytest.mark.parametrize("amount,ratios,expected", ALLOCATE_VECTORS)
def test_allocate_vectors(amount, ratios, expected):
    assert allocate(amount, ratios) == expected


APPLY_RATE_VECTORS = [
    (100, "1.1", 110),
    (1005, "0.5", 502),   # 502.5 -> even
    (1015, "0.5", 508),   # 507.5 -> even
    (1, "0.5", 0),        # 0.5 -> 0
    (3, "0.5", 2),        # 1.5 -> 2
    (-5, "0.5", -2),      # -2.5 -> -2
    (-15, "0.5", -8),     # -7.5 -> -8
    (0, "5.25", 0),
    (999, "0.0001", 0),
    (10000, "0.00005", 0),  # 0.5 -> even
]


@pytest.mark.parametrize("amount,rate,expected", APPLY_RATE_VECTORS)
def test_apply_rate_vectors(amount, rate, expected):
    result = apply_rate(amount, rate)
    assert result == expected
    assert type(result) is int


def test_apply_rate_rounding_mode_is_half_even_not_half_up():
    # Would fail if the mode changed to HALF_UP/HALF_DOWN/floor/ceil.
    assert [apply_rate(n, "0.5") for n in (1, 3, 5, 7)] == [0, 2, 2, 4]


# ------------------------------------------------------------- properties

@PROP
@given(
    amount=st.integers(-10**12, 10**12),
    ratios=st.lists(st.integers(0, 1000), min_size=1, max_size=12).filter(lambda r: sum(r) > 0),
)
def test_allocate_preserves_sum_and_is_int(amount, ratios):
    shares = allocate(amount, ratios)
    assert sum(shares) == amount  # no cent lost or created
    assert len(shares) == len(ratios)
    assert all(type(s) is int for s in shares)


@PROP
@given(
    amount=st.integers(0, 10**12),
    ratios=st.lists(st.integers(0, 1000), min_size=1, max_size=12).filter(lambda r: sum(r) > 0),
)
def test_allocate_is_fair_for_nonnegative(amount, ratios):
    shares = allocate(amount, ratios)
    assert all(s >= 0 for s in shares)
    for s, r in zip(shares, ratios):
        exact = Decimal(amount) * r / sum(ratios)
        assert abs(Decimal(s) - exact) < 1  # within one minor unit of exact
        if r == 0:
            assert s == 0


@PROP
@given(amount=st.integers(0, 10**9), n=st.integers(1, 20))
def test_allocate_equal_ratios_differ_by_at_most_one(amount, n):
    shares = allocate(amount, [1] * n)
    assert max(shares) - min(shares) <= 1


@PROP
@given(
    cur=st.sampled_from(sorted(EXPONENTS)),
    minor=st.integers(-10**15, 10**15),
)
def test_to_minor_round_trips_with_exact_formatting(cur, minor):
    exp = EXPONENTS[cur]
    text = format(Decimal(minor).scaleb(-exp), "f")  # independent formatter
    assert to_minor(text, cur) == minor


@PROP
@given(amount=st.integers(-10**12, 10**12))
def test_apply_rate_identity_and_type(amount):
    assert apply_rate(amount, "1") == amount
    assert apply_rate(amount, "0") == 0
    assert type(apply_rate(amount, "1.5")) is int


@PROP
@given(amount=st.integers(-10**12, 10**12), rate=st.decimals(0, 10, places=6))
def test_apply_rate_within_half_unit_of_exact(amount, rate):
    result = apply_rate(amount, str(rate))
    assert abs(Decimal(result) - Decimal(amount) * rate) <= Decimal("0.5")


@PROP
@given(amount=st.integers(-10**12, 10**12), rate=st.decimals(0, 10, places=6))
def test_apply_rate_is_sign_symmetric(amount, rate):
    # half-even is symmetric around zero
    assert apply_rate(-amount, str(rate)) == -apply_rate(amount, str(rate))


# ------------------------------------------------------------ error paths

def test_to_minor_unknown_currency_raises():
    with pytest.raises(KeyError):
        to_minor("1.00", "XXX")


def test_to_minor_garbage_raises():
    with pytest.raises(Exception):
        to_minor("abc", "USD")


def test_allocate_zero_total_raises():
    with pytest.raises(ZeroDivisionError):
        allocate(100, [0, 0])


def test_allocate_empty_ratios_raises():
    with pytest.raises(ZeroDivisionError):
        allocate(100, [])


# ----------------------------------------------- known defects (reported)
# These describe what money code should do; the current module does not.
# strict xfail: they turn red-to-fix when the module is corrected.

@pytest.mark.xfail(strict=True, reason="to_minor silently truncates excess precision")
@pytest.mark.parametrize("amount,cur", [("19.999", "USD"), ("0.5", "JPY"), ("1.0005", "BHD")])
def test_to_minor_rejects_sub_minor_unit_precision(amount, cur):
    with pytest.raises(ValueError):
        to_minor(amount, cur)


@pytest.mark.xfail(strict=True, reason="to_minor accepts NaN/Infinity input as a different error type")
@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_to_minor_rejects_non_finite_with_valueerror(amount):
    with pytest.raises(ValueError):
        to_minor(amount, "USD")
