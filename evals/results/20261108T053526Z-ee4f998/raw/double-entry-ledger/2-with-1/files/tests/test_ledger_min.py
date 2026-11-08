import dataclasses
import random
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ledger_min import Entry, Ledger, Posting  # noqa: E402

D = date(2026, 10, 15)


def P(acct, side, amt, cur="BRL"):
    return Posting(acct, side, amt, cur)


def E(id, postings, ref=None, d=D):
    return Entry(id, d, tuple(postings), ref or id)


def simple(id="e1", amt=1000, ref=None):
    return E(id, [P("cash", "debit", amt), P("rev", "credit", amt)], ref)


def test_balanced_posts():
    l = Ledger()
    l.post(simple())
    assert l.balance("cash", "BRL") == 1000


def test_unbalanced_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("e", [P("a", "debit", 10), P("b", "credit", 9)]))


def test_single_posting_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("e", [P("a", "debit", 10)]))


def test_balanced_in_total_not_per_currency_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("e", [P("a", "debit", 10, "BRL"), P("b", "credit", 10, "USD")]))


@pytest.mark.parametrize("amt", [0, -5])
def test_non_positive_amount_raises(amt):
    with pytest.raises(ValueError):
        P("a", "debit", amt)


def test_immutable():
    e = simple()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.external_ref = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 1


def test_reversal_nets_to_prior_balance():
    l = Ledger()
    l.post(simple("e1", 1000))
    l.reverse("e1", id="r1", effective_date=D, external_ref="r1")
    assert l.balance("cash", "BRL") == 0 and l.balance("rev", "BRL") == 0


def test_correct_wrong_amount():
    l = Ledger()
    l.post(simple("e1", 1500))  # wrong: should be 1000
    rev, new = l.correct(
        "e1", (P("cash", "debit", 1000), P("rev", "credit", 1000)),
        effective_date=date(2026, 11, 8), ref_prefix="fix-e1",
    )
    assert l.balance("cash", "BRL") == 1000
    assert l.balance("rev", "BRL") == -1000
    assert rev.reverses == "e1" and new.corrects == "e1"
    assert l.entries[0].postings[0].amount_minor == 1500  # original untouched


def test_closed_period_refused_and_adjustment_in_open_period_ok():
    l = Ledger(closed_through=date(2026, 10, 31))
    with pytest.raises(ValueError):
        l.post(simple("old", d=None) if False else E("old", simple().postings, d=D))
    l.post(E("adj", simple().postings, d=date(2026, 11, 1)))


def test_correct_into_closed_period_refused():
    l = Ledger()
    l.post(simple("e1"))
    l.closed_through = date(2026, 10, 31)
    with pytest.raises(ValueError):
        l.correct("e1", simple().postings, effective_date=D, ref_prefix="f")


def test_same_external_ref_is_noop():
    l = Ledger()
    first = l.post(simple("e1", ref="ext"))
    second = l.post(simple("e2", 999, ref="ext"))
    assert second is first and len(l.entries) == 1


def test_correct_is_idempotent():
    l = Ledger()
    l.post(simple("e1", 1500))
    args = ("e1", (P("cash", "debit", 1000), P("rev", "credit", 1000)))
    kw = dict(effective_date=date(2026, 11, 8), ref_prefix="fix")
    l.correct(*args, **kw)
    l.correct(*args, **kw)
    assert len(l.entries) == 3 and l.balance("cash", "BRL") == 1000


def test_trial_balance_random():
    rnd = random.Random(1)
    l = Ledger()
    accts = ["a", "b", "c", "d"]
    for i in range(200):
        x, y = rnd.sample(accts, 2)
        amt = rnd.randint(1, 10_000)
        l.post(E(f"e{i}", [P(x, "debit", amt), P(y, "credit", amt)]))
    assert sum(l.balance(a, "BRL") for a in accts) == 0
