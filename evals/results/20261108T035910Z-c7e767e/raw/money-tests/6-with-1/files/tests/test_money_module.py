"""Frozen vectors (hand-computed, to be reviewed by a person) and seeded property tests."""
import pathlib
import sys

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from money_module import allocate, apply_rate, to_minor  # noqa: E402

TO_MINOR = [
    ("12.34", "USD", 1234),
    ("0.01", "BRL", 1),
    ("0", "USD", 0),
    ("100", "JPY", 100),
    ("1.234", "BHD", 1234),
    ("-5.50", "USD", -550),
    ("1", "BHD", 1000),
]

ALLOCATE = [
    (100, [1, 1, 1], [34, 33, 33]),
    (5, [1, 1], [3, 2]),
    (1, [1, 1, 1], [1, 0, 0]),
    (0, [1, 2], [0, 0]),
    (10, [3, 7], [3, 7]),
    (100, [50, 25, 25], [50, 25, 25]),
    (-100, [1, 1, 1], [-33, -33, -34]),
    (10, [1], [10]),
    (7, [2, 1], [5, 2]),
    (10, [1, 2], [3, 7]),
]

# Banker's rounding (ROUND_HALF_EVEN) at exact halves, both parities and signs.
APPLY_RATE = [
    (1000, "0.125", 125),
    (5, "0.5", 2),
    (7, "0.5", 4),
    (15, "0.1", 2),
    (25, "0.1", 2),
    (-5, "0.5", -2),
    (-7, "0.5", -4),
    (100, "1.0", 100),
    (100, "0", 0),
    (3, "0.4", 1),
    (3, "0.6", 2),
]


@pytest.mark.parametrize("amount,cur,expected", TO_MINOR)
def test_to_minor_vectors(amount, cur, expected):
    result = to_minor(amount, cur)
    assert result == expected
    assert type(result) is int


def test_to_minor_unknown_currency():
    with pytest.raises(KeyError):
        to_minor("1", "XXX")


@pytest.mark.parametrize("amount,ratios,expected", ALLOCATE)
def test_allocate_vectors(amount, ratios, expected):
    assert allocate(amount, ratios) == expected


@pytest.mark.parametrize("amount,rate,expected", APPLY_RATE)
def test_apply_rate_vectors(amount, rate, expected):
    result = apply_rate(amount, rate)
    assert result == expected
    assert type(result) is int


@settings(max_examples=500, derandomize=True)
@given(
    st.integers(min_value=-10**12, max_value=10**12),
    st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=10),
)
def test_allocate_preserves_sum_and_is_fair(amount, ratios):
    shares = allocate(amount, ratios)
    assert len(shares) == len(ratios)
    assert sum(shares) == amount
    total = sum(ratios)
    for share, r in zip(shares, ratios):
        exact = amount * r / total
        assert abs(share - exact) < 1
        assert type(share) is int


@settings(max_examples=300, derandomize=True)
@given(
    st.integers(min_value=0, max_value=10**9),
    st.sampled_from(["USD", "BRL", "JPY", "BHD"]),
)
def test_to_minor_roundtrip(minor, cur):
    from money_module import EXPONENTS
    exp = EXPONENTS[cur]
    text = f"{minor // 10**exp}.{str(minor % 10**exp).zfill(exp)}" if exp else str(minor)
    assert to_minor(text, cur) == minor


@settings(max_examples=300, derandomize=True)
@given(st.integers(min_value=-10**9, max_value=10**9), st.integers(min_value=0, max_value=1000))
def test_apply_rate_within_half_unit(amount, permille):
    result = apply_rate(amount, f"{permille / 1000:.3f}")
    assert abs(result - amount * permille / 1000) <= 0.5
