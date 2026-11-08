"""Test vectors for double-entry-ledger.

Run against the reference: `pytest skills/double-entry-ledger`.
Run against your module:   `LEDGER_SOLUTION=/path/to/ledger.py pytest skills/double-entry-ledger`.

The module under test must expose Posting(account, side, amount, currency),
Entry(id, effective_date, postings, external_ref, description="", reverses=None) and a Ledger
with post, close, balance, reverse and trial_balance, raising on invalid input (any exception).
"""
from __future__ import annotations

import dataclasses
import importlib.util
import os
import sys
import random
from datetime import date
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("LEDGER_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("ledger_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
D = date(2026, 3, 10)


def P(account, side, amount, ccy="BRL"):
    return m.Posting(account, side, amount, ccy)


def capture(entry_id="e1", ref="pay_1", on=D):
    # 100.00 captured, 2.90 fee, 5.00 kept as revenue, 95.00 owed to the customer
    return m.Entry(entry_id, on, (
        P("1020", "debit", 9710), P("5010", "debit", 290),
        P("2010", "credit", 9500), P("4010", "credit", 500),
    ), ref, "capture")


def test_balanced_entry_posts():
    L = m.Ledger()
    L.post(capture())
    assert L.balance("1020", "BRL") == 9710
    assert L.balance("2010", "BRL") == -9500
    assert L.balance("4010", "BRL") == -500
    assert L.balance("5010", "BRL") == 290


def test_unbalanced_entry_raises():
    L = m.Ledger()
    with pytest.raises(Exception):
        L.post(m.Entry("e", D, (P("1020", "debit", 100), P("2010", "credit", 99)), "r1"))


def test_single_posting_raises():
    L = m.Ledger()
    with pytest.raises(Exception):
        L.post(m.Entry("e", D, (P("1020", "debit", 100),), "r1"))


def test_balanced_per_currency_passes_and_cross_currency_fails():
    L = m.Ledger()
    L.post(m.Entry("fx", D, (
        P("1010", "debit", 500, "USD"), P("3010", "credit", 500, "USD"),
        P("3010", "debit", 2500, "BRL"), P("1011", "credit", 2500, "BRL"),
    ), "fx1"))
    with pytest.raises(Exception):
        L.post(m.Entry("bad", D, (P("1010", "debit", 500, "USD"), P("1011", "credit", 2500, "BRL")), "fx2"))


@pytest.mark.parametrize("amount", [0, -1])
def test_non_positive_amount_raises(amount):
    L = m.Ledger()
    with pytest.raises(Exception):
        L.post(m.Entry("e", D, (P("1020", "debit", amount), P("2010", "credit", amount)), "r"))


def test_entries_are_immutable():
    e = capture()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.description = "edited"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount = 1  # type: ignore[misc]


def test_reversal_nets_to_prior_balance():
    L = m.Ledger()
    L.post(capture())
    L.reverse("e1", D, "e1r", "pay_1_rev")
    for acct in ("1020", "5010", "2010", "4010"):
        assert L.balance(acct, "BRL") == 0
    assert L.entries[-1].reverses == "e1"


def test_closed_period_refuses_backdated_entries():
    L = m.Ledger()
    L.post(capture())
    L.close(date(2026, 3, 31))
    with pytest.raises(Exception):
        L.post(capture("e2", "pay_2", on=date(2026, 3, 31)))
    L.post(capture("e3", "pay_3", on=date(2026, 4, 1)))
    # correcting a closed-period entry happens in the open period
    rev = L.reverse("e1", date(2026, 4, 2), "e1r", "pay_1_rev")
    assert rev.effective_date == date(2026, 4, 2)


def test_same_external_reference_is_idempotent():
    L = m.Ledger()
    first = L.post(capture())
    again = L.post(capture("e1-dup", "pay_1"))
    assert again is first
    assert len(L.entries) == 1
    assert L.balance("1020", "BRL") == 9710


def test_balance_as_of_uses_effective_date():
    L = m.Ledger()
    L.post(capture("a", "p1", on=date(2026, 1, 5)))
    L.post(capture("b", "p2", on=date(2026, 2, 5)))
    assert L.balance("1020", "BRL", as_of=date(2026, 1, 31)) == 9710
    assert L.balance("1020", "BRL") == 19420


def test_trial_balance_after_random_entries():
    L = m.Ledger()
    rng = random.Random(3)
    accounts = ["1010", "1020", "2010", "4010", "5010"]
    for i in range(300):
        amt = rng.randint(1, 10_000_00)
        a, b = rng.sample(accounts, 2)
        split = rng.randint(1, amt)
        L.post(m.Entry(f"e{i}", D, (
            P(a, "debit", amt), P(b, "credit", split), P("4010", "credit", amt - split),
        ) if amt - split > 0 else (P(a, "debit", amt), P(b, "credit", amt)), f"ref{i}"))
    debits, credits = L.trial_balance()
    assert debits == credits
    assert sum(L.balance(acc, "BRL") for acc in accounts) == 0
