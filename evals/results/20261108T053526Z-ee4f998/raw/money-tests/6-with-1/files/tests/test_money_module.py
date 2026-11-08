"""Tests for src/money_module.py. Written without a shell: UNRUN."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from money_module import allocate, apply_rate, to_minor  # noqa: E402

# Frozen vectors: expected values computed by hand, not by the code under test.
TO_MINOR = [
    ("10.25", "USD", 1025),
    ("0.01", "BRL", 1),
    ("0", "USD", 0),
    ("10", "JPY", 10),
    ("1.234", "BHD", 1234),
    ("-5.50", "USD", -550),
    ("1234567890.99", "USD", 123456789099),
]
ALLOCATE = [
    (100, [1, 1, 1], [34, 33, 33]),
    (100, [50, 50], [50, 50]),
    (5, [1, 1], [3, 2]),
    (0, [1, 2], [0, 0]),
    (10, [1, 2], [3, 7]),
    (1, [1, 1, 1], [1, 0, 0]),
    (100, [100], [100]),
]
APPLY_RATE = [
    (100, "0.025", 2),    # 2.5 -> even
    (101, "0.025", 3),    # 2.525 -> up
    (150, "0.01", 2),     # 1.5 -> even
    (250, "0.01", 2),     # 2.5 -> even
    (100, "1.5", 150),
    (0, "0.5", 0),
    (-250, "0.01", -2),   # -2.5 -> even
    (1000, "0", 0),
]


@pytest.mark.parametrize("amount,cur,expected", TO_MINOR)
def test_to_minor_vectors(amount, cur, expected):
    result = to_minor(amount, cur)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize("amount,ratios,expected", ALLOCATE)
def test_allocate_vectors(amount, ratios, expected):
    assert allocate(amount, ratios) == expected


@pytest.mark.parametrize("amount,rate,expected", APPLY_RATE)
def test_apply_rate_vectors(amount, rate, expected):
    result = apply_rate(amount, rate)
    assert result == expected
    assert type(result) is int


def test_to_minor_unknown_currency_raises():
    with pytest.raises(KeyError):
        to_minor("1.00", "XXX")


def test_allocate_properties():
    rng = random.Random(20261108)
    for _ in range(500):
        amount = rng.randint(0, 10**9)
        ratios = [rng.randint(1, 1000) for _ in range(rng.randint(1, 8))]
        shares = allocate(amount, ratios)
        assert sum(shares) == amount  # no cent lost or created
        assert len(shares) == len(ratios)
        assert all(type(s) is int and s >= 0 for s in shares)
        total = sum(ratios)
        for s, r in zip(shares, ratios):  # each within one unit of exact share
            assert abs(s * total - amount * r) < total


def test_to_minor_round_trip_properties():
    rng = random.Random(7)
    for cur, exp in (("JPY", 0), ("USD", 2), ("BHD", 3)):
        for _ in range(200):
            minor = rng.randint(-10**9, 10**9)
            sign = "-" if minor < 0 else ""
            digits = str(abs(minor)).rjust(exp + 1, "0")
            text = sign + (digits[:-exp] + "." + digits[-exp:] if exp else digits)
            assert to_minor(text, cur) == minor


def test_apply_rate_properties():
    rng = random.Random(11)
    for _ in range(300):
        amount = rng.randint(-10**9, 10**9)
        assert apply_rate(amount, "1") == amount
        assert apply_rate(amount, "0") == 0
        rate_bp = rng.randint(0, 20000)
        rate = f"{rate_bp // 10000}.{rate_bp % 10000:04d}"
        result = apply_rate(amount, rate)
        assert abs(result * 10000 - amount * rate_bp) <= 5000
