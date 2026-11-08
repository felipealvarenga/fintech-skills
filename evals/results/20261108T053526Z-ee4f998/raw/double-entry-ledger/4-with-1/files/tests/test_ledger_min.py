import dataclasses
import os
import random
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger_min import Entry, Ledger, Posting  # noqa: E402

D = date(2026, 1, 10)


def P(acct, side, amt, ccy="BRL"):
    return Posting(acct, side, amt, ccy)


def E(ref, *postings, d=D):
    return Entry(ref, d, tuple(postings), ref)


def simple(ref="r1", amt=100):
    return E(ref, P("cash", "debit", amt), P("cust", "credit", amt))


def test_balanced_posts_and_updates_cache():
    l = Ledger()
    l.post(simple())
    assert l.balance("cash", "BRL") == 100
    assert l.balance("cust", "BRL") == -100


def test_unbalanced_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("x", P("a", "debit", 10), P("b", "credit", 9)))


def test_single_posting_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("x", P("a", "debit", 10)))


def test_balanced_in_total_not_per_currency_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("x", P("a", "debit", 10, "BRL"), P("b", "credit", 10, "USD")))


@pytest.mark.parametrize("amt", [0, -5])
def test_non_positive_amount_raises(amt):
    with pytest.raises(ValueError):
        Ledger().post(E("x", P("a", "debit", amt), P("b", "credit", amt)))


def test_failed_post_leaves_cache_untouched():
    l = Ledger()
    with pytest.raises(ValueError):
        l.post(E("x", P("a", "debit", 10), P("b", "credit", 9)))
    assert l.balance("a", "BRL") == 0 and l.entries == []


def test_immutable():
    l = Ledger()
    e = l.post(simple())
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.external_ref = "z"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 1
    assert isinstance(e.postings, tuple)


def test_reversal_nets_to_prior():
    l = Ledger()
    l.post(simple("a", 50))
    before = l.balance("cash", "BRL")
    l.post(simple("b", 30))
    l.post(E("b-rev", P("cash", "credit", 30), P("cust", "debit", 30)))
    assert l.balance("cash", "BRL") == before
    assert l.reconcile() == []


def test_closed_period():
    l = Ledger(closed_through=date(2026, 1, 31))
    with pytest.raises(ValueError):
        l.post(simple("old"))
    l.post(E("adj", P("cash", "debit", 5), P("cust", "credit", 5), d=date(2026, 2, 1)))
    assert l.balance("cash", "BRL") == 5


def test_idempotent_external_ref():
    l = Ledger()
    first = l.post(simple("dup", 100))
    second = l.post(simple("dup", 999))
    assert second is first
    assert len(l.entries) == 1
    assert l.balance("cash", "BRL") == 100


def test_trial_balance_and_cache_matches_derivation():
    rnd = random.Random(1)
    l = Ledger()
    accts = ["a", "b", "c", "d"]
    for i in range(200):
        x, y = rnd.sample(accts, 2)
        amt = rnd.randint(1, 1000)
        l.post(E(f"e{i}", P(x, "debit", amt), P(y, "credit", amt)))
    debits = sum(p.amount_minor for e in l.entries for p in e.postings if p.side == "debit")
    credits = sum(p.amount_minor for e in l.entries for p in e.postings if p.side == "credit")
    assert debits == credits
    assert l.reconcile() == []
    for a in accts:
        assert l.balance(a, "BRL") == l.derived_balance(a, "BRL")


def test_reconcile_detects_drift_and_rebuild_repairs():
    l = Ledger()
    l.post(simple())
    l._cache[("cash", "BRL")] = 1  # simulate drift
    assert l.reconcile() == [("cash", "BRL", 1, 100)]
    l.rebuild_cache()
    assert l.reconcile() == []
