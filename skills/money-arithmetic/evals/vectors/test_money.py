"""Test vectors for money-arithmetic.

Run against the reference: `pytest skills/money-arithmetic`.
Run against your module:   `MONEY_SOLUTION=/path/to/money.py pytest skills/money-arithmetic`.

The module under test must expose: to_minor, from_minor, add, allocate, apply_rate, convert,
and raise on unknown currencies, invalid amounts and currency mismatches (any exception type).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import random
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("MONEY_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("money_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


@pytest.mark.parametrize("amount,ccy,minor", [
    ("12.34", "USD", 1234),
    ("0.01", "BRL", 1),
    ("-0.01", "EUR", -1),
    ("5", "JPY", 5),
    ("12.345", "BHD", 12345),
    ("1000000.00", "USD", 100000000),
])
def test_to_minor(amount, ccy, minor):
    assert m.to_minor(amount, ccy) == minor
    assert isinstance(m.to_minor(amount, ccy), int)


@pytest.mark.parametrize("amount,ccy", [
    ("12.345", "USD"),
    ("1.5", "JPY"),
    ("0.0001", "BHD"),
    ("NaN", "USD"),
    ("Infinity", "USD"),
    ("abc", "USD"),
])
def test_to_minor_refuses_invalid(amount, ccy):
    with pytest.raises(Exception):
        m.to_minor(amount, ccy)


def test_unknown_currency_is_refused():
    with pytest.raises(Exception):
        m.to_minor("1.00", "XXX")
    with pytest.raises(Exception):
        m.from_minor(100, "ZZZ")


@pytest.mark.parametrize("minor,ccy,text", [
    (1234, "USD", "12.34"),
    (5, "USD", "0.05"),
    (-1, "USD", "-0.01"),
    (5, "JPY", "5"),
    (12345, "BHD", "12.345"),
    (0, "BRL", "0.00"),
])
def test_from_minor(minor, ccy, text):
    assert m.from_minor(minor, ccy) == text


@pytest.mark.parametrize("ccy", ["USD", "JPY", "BHD"])
def test_round_trip(ccy):
    rng = random.Random(7)
    for _ in range(200):
        x = rng.randint(-10**9, 10**9)
        assert m.to_minor(m.from_minor(x, ccy), ccy) == x


def test_add_same_currency():
    assert m.add((100, "USD"), (250, "USD")) == (350, "USD")


def test_add_refuses_mixed_currency():
    with pytest.raises(Exception):
        m.add((100, "USD"), (100, "BRL"))


@pytest.mark.parametrize("amount,ratios,expected", [
    (100, [1, 1, 1], [34, 33, 33]),
    (10, [1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1]),
    (-100, [1, 1, 1], [-34, -33, -33]),
    (100, [1, 0, 1], [50, 0, 50]),
    (1, [1, 1], [1, 0]),
    (0, [3, 2], [0, 0]),
    (1000, [70, 30], [700, 300]),
    (1001, [70, 30], [701, 300]),
])
def test_allocate_vectors(amount, ratios, expected):
    assert m.allocate(amount, ratios) == expected


def test_allocate_preserves_sum_and_fairness():
    rng = random.Random(42)
    for _ in range(500):
        amount = rng.randint(-10**7, 10**7)
        n = rng.randint(1, 9)
        ratios = [rng.randint(0, 50) for _ in range(n)]
        if sum(ratios) == 0:
            ratios[0] = 1
        parts = m.allocate(amount, ratios)
        assert len(parts) == n
        assert sum(parts) == amount
        total = sum(ratios)
        for part, r in zip(parts, ratios):
            exact = amount * r / total
            assert abs(part - exact) < 1 + 1e-9
            if r == 0:
                assert part == 0


def test_allocate_refuses_bad_ratios():
    with pytest.raises(Exception):
        m.allocate(100, [])
    with pytest.raises(Exception):
        m.allocate(100, [0, 0])
    with pytest.raises(Exception):
        m.allocate(100, [1, -1])


def test_apply_rate_rounding_policy_is_visible():
    assert m.apply_rate(1000, "0.0315") == 32
    assert m.apply_rate(1000, "0.0325", ROUND_HALF_EVEN) == 32
    assert m.apply_rate(1000, "0.0325", ROUND_HALF_UP) == 33
    assert m.apply_rate(-1000, "0.0325", ROUND_HALF_UP) == -33
    assert isinstance(m.apply_rate(1000, "0.0315"), int)


@pytest.mark.parametrize("amount,src,dst,rate,expected", [
    (1000, "USD", "BRL", "5.1234", 5123),
    (1000, "USD", "JPY", "150.5", 1505),
    (1505, "JPY", "USD", "0.0066445", 1000),
    (12345, "BHD", "USD", "2.65", 3271),
    (100, "USD", "USD", "1", 100),
])
def test_convert(amount, src, dst, rate, expected):
    out = m.convert(amount, src, dst, rate)
    assert out == expected
    assert isinstance(out, int)
