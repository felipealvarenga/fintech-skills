"""Test vectors for interest-and-amortization.

Run against the reference: `pytest skills/interest-and-amortization`.
Run against your module:   `AMORT_SOLUTION=/path/to/amortization.py pytest skills/interest-and-amortization`.

The module under test must expose price_schedule, sac_schedule, simple_interest and
effective_to_periodic with the signatures used below. Amounts are integers in minor units.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("AMORT_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("amort_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _residual_bound(rate: str, n: int) -> int:
    """Rounding the installment once (error <= 0.5) compounds over the term, and each period's
    interest rounding adds <= 0.5: bound = 0.5 * ((1+i)^n - 1) / i + 0.5 * n (n when i == 0)."""
    i = Decimal(rate)
    growth = Decimal(n) if i == 0 else ((1 + i) ** n - 1) / i
    return int((Decimal("0.5") * growth + Decimal("0.5") * n).to_integral_value()) + 1



def test_price_known_installment():
    rows = m.price_schedule(100_000, "0.01", 12)
    assert rows[0]["installment"] == 8885
    assert rows[0]["interest"] == 1000
    assert rows[0]["principal"] == 7885


@pytest.mark.parametrize("principal,rate,n", [
    (100_000, "0.01", 12), (250_000, "0.0199", 24), (1_000_000, "0.035", 60),
    (999, "0.1", 3), (100_000, "0", 10), (123_456, "0.0123", 7),
])
def test_price_invariants(principal, rate, n):
    rows = m.price_schedule(principal, rate, n)
    assert len(rows) == n
    assert sum(r["principal"] for r in rows) == principal
    assert rows[-1]["balance"] == 0
    assert all(r["interest"] >= 0 and r["principal"] >= 0 for r in rows)
    installments = {r["installment"] for r in rows[:-1]}
    assert len(installments) == 1
    assert abs(rows[-1]["installment"] - rows[0]["installment"]) <= _residual_bound(rate, n)
    for r in rows:
        assert r["installment"] == r["interest"] + r["principal"]
        assert all(isinstance(r[k], int) for k in ("installment", "interest", "principal", "balance"))


def test_sac_known_values():
    rows = m.sac_schedule(100_000, "0.01", 12)
    assert [r["principal"] for r in rows[:-1]] == [8333] * 11
    assert rows[-1]["principal"] == 8337
    assert rows[0]["interest"] == 1000
    assert rows[0]["installment"] == 9333
    assert sum(r["principal"] for r in rows) == 100_000
    assert rows[-1]["balance"] == 0
    assert all(rows[k]["installment"] >= rows[k + 1]["installment"] for k in range(10))


def test_single_period():
    rows = m.price_schedule(50_000, "0.02", 1)
    assert len(rows) == 1
    assert rows[0] == {"period": 1, "installment": 51_000, "interest": 1000, "principal": 50_000, "balance": 0}


def test_simple_interest_known_value_and_day_count():
    assert m.simple_interest(100_000, "0.12", 30) == 986
    assert m.simple_interest(100_000, "0.12", 30, basis=360) == 1000
    # leap year: 366 days at ACT/365 is more than one year of interest
    assert m.simple_interest(100_000, "0.12", 366) == 12_033
    assert m.simple_interest(100_000, "0.12", 366, basis=366) == 12_000


def test_rounding_policy_is_visible():
    # 100.00 at 0.5% for 1 period: interest exactly 0.50 -> HALF_UP 1? no: 50.0 minor units exact.
    # Use 1.25 cents: 125 * 0.01 = 1.25 -> HALF_UP 1, HALF_EVEN 1; need a .5 case: 150 * 0.01 = 1.5
    up = m.simple_interest(150, "0.01", 365, basis=365, rounding=ROUND_HALF_UP)
    even = m.simple_interest(150, "0.01", 365, basis=365, rounding=ROUND_HALF_EVEN)
    assert (up, even) == (2, 2)
    up = m.simple_interest(250, "0.01", 365, basis=365, rounding=ROUND_HALF_UP)
    even = m.simple_interest(250, "0.01", 365, basis=365, rounding=ROUND_HALF_EVEN)
    assert (up, even) == (3, 2)


def test_effective_to_periodic():
    monthly = m.effective_to_periodic("0.12", 12)
    assert isinstance(monthly, Decimal)
    assert monthly == Decimal("0.009488792935")
    assert m.effective_to_periodic("0", 12) == 0


def test_invalid_inputs_raise():
    with pytest.raises(Exception):
        m.price_schedule(0, "0.01", 12)
    with pytest.raises(Exception):
        m.sac_schedule(1000, "0.01", 0)
