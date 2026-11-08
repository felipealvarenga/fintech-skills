"""Test vectors for money-tests.

Run against the reference: `pytest skills/money-tests`.
Run against your module:   `MONEYTESTS_SOLUTION=/path/to/lint.py pytest skills/money-tests`.

The module under test must expose lint_tests(source) returning findings with .code and .line,
kill_rate(killed, survived, errors=0, timeouts=0) and meets_gate(rate, threshold=0.8).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import textwrap
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("MONEYTESTS_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("moneytests_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


def codes(source: str) -> list[tuple[str, int]]:
    return [(f.code, f.line) for f in m.lint_tests(textwrap.dedent(source))]


def test_clean_money_test_has_no_findings():
    src = '''
    import random
    from decimal import ROUND_HALF_EVEN

    def test_allocate_preserves_sum():
        rng = random.Random(42)
        for _ in range(200):
            amount = rng.randint(-10**7, 10**7)
            parts = allocate(amount, [1, 1, 1])
            assert sum(parts) == amount

    def test_rate_rounding_policy_is_visible():
        assert apply_rate(1000, "0.0325", ROUND_HALF_EVEN) == 32

    def test_mixed_currency_raises():
        with pytest.raises(CurrencyMismatch):
            add((1, "USD"), (1, "BRL"))
    '''
    assert codes(src) == []


def test_wall_clock_and_sleep_are_flagged():
    src = '''
    def test_due_date():
        today = datetime.now()
        time.sleep(1)
        assert schedule(today)[0]["due"] > today
    '''
    assert ("wall-clock", 3) in codes(src)
    assert ("sleep", 4) in codes(src)


def test_live_network_is_flagged_unless_faked():
    live = '''
    def test_charge():
        resp = stripe.PaymentIntent.create(amount=100)
        assert resp.status == "succeeded"
    '''
    faked = '''
    def test_charge(monkeypatch):
        monkeypatch.setattr(stripe.PaymentIntent, "create", lambda **k: FakeIntent())
        assert charge(100)["status"] == "succeeded"
    '''
    assert ("live-network", 3) in codes(live)
    assert all(c != "live-network" for c, _ in codes(faked))


def test_unseeded_random_is_flagged_and_seeded_is_not():
    unseeded = '''
    def test_split():
        amount = random.randint(1, 100)
        assert sum(allocate(amount, [1, 1])) == amount
    '''
    seeded = '''
    def test_split():
        rng = random.Random(1)
        amount = rng.randint(1, 100)
        assert sum(allocate(amount, [1, 1])) == amount
    '''
    assert ("unseeded-random", 3) in codes(unseeded)
    assert codes(seeded) == []


def test_approximate_money_and_weak_assertions_are_flagged():
    src = '''
    def test_total():
        assert total == pytest.approx(19.99)

    def test_fee():
        result = compute_fee(1000)
        assert result is not None
    '''
    assert ("approximate-money", 3) in codes(src)
    assert ("weak-assertion", 7) in codes(src)


def test_test_without_assertion_is_flagged():
    src = '''
    def test_runs_without_error():
        compute_schedule(100000, "0.01", 12)

    def test_raises():
        with pytest.raises(ValueError):
            compute_schedule(0, "0.01", 12)
    '''
    found = codes(src)
    assert ("no-assertion", 2) in found
    assert all(not (c == "no-assertion" and line == 5) for c, line in found)


def test_syntax_error_is_reported_not_raised():
    assert codes("def test_x(:\n    pass\n")[0][0] == "syntax-error"


@pytest.mark.parametrize("killed,survived,errors,timeouts,expected", [
    (34, 66, 0, 0, 0.34),
    (80, 20, 5, 3, 0.8),    # errors and timeouts are excluded from the denominator
    (0, 0, 4, 0, None),
    (1, 0, 0, 0, 1.0),
    (7, 3, 0, 0, 0.7),
])
def test_kill_rate(killed, survived, errors, timeouts, expected):
    assert m.kill_rate(killed, survived, errors, timeouts) == expected


def test_kill_rate_refuses_negative_counts():
    with pytest.raises(Exception):
        m.kill_rate(-1, 1)


def test_gate():
    assert m.meets_gate(0.8) is True
    assert m.meets_gate(0.79) is False
    assert m.meets_gate(None) is False
    assert m.meets_gate(0.5, threshold=0.5) is True
