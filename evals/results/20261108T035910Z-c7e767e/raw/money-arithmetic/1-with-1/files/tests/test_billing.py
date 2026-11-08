import random
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from billing import split_and_store
from money import Money, allocate, apply_rate, from_minor, to_minor


def test_invoice_100_brl_50_30_20():
    conn = sqlite3.connect(":memory:")
    shares = split_and_store(conn, "INV-1", Money(10000, "BRL"))
    assert [s.minor for s in shares.values()] == [5000, 3000, 2000]
    rows = conn.execute("SELECT partner, amount_minor, currency FROM invoice_shares ORDER BY partner").fetchall()
    assert rows == [("partner_a", 5000, "BRL"), ("partner_b", 3000, "BRL"), ("partner_c", 2000, "BRL")]


def test_odd_total_keeps_sum():
    assert allocate(10001, [50, 30, 20]) == [5001, 3000, 2000]
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]


def test_allocation_properties():
    rnd = random.Random(1)
    for _ in range(2000):
        total = rnd.randint(-10**6, 10**6)
        ratios = [rnd.choice([0, 1, 2, 3, 20, 30, 50]) for _ in range(rnd.randint(1, 6))]
        if sum(ratios) == 0:
            continue
        parts = allocate(total, ratios)
        assert sum(parts) == total
        for p, r in zip(parts, ratios):
            assert abs(p - total * r / sum(ratios)) < 1
            assert r > 0 or p == 0


def test_round_trip_and_parsing():
    for ccy in ("JPY", "BRL", "KWD"):
        for x in (0, 5, 1234, -1234):
            assert to_minor(from_minor(x, ccy), ccy) == x
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")
    with pytest.raises(ValueError):
        to_minor("NaN", "USD")
    with pytest.raises(ValueError):
        Money(1, "XXX")


def test_mixed_currency_refused():
    with pytest.raises(ValueError):
        Money(1, "USD") + Money(1, "BRL")


def test_rate_policy():
    assert apply_rate(1000, "0.0325") == 32  # HALF_EVEN
