import dataclasses
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ledger_min import Entry, Ledger, PeriodClosedError, Posting  # noqa: E402


def P(acct, side, amt, cur="USD"):
    return Posting(acct, side, amt, cur)


def E(id, d, postings, ref=None):
    return Entry(id, d, tuple(postings), ref or id)


OCT = date(2026, 10, 15)


def simple(id="e1", d=OCT, amt=100):
    return E(id, d, [P("cash", "debit", amt), P("rev", "credit", amt)])


def test_balanced_posts_unbalanced_raises():
    l = Ledger()
    l.post(simple())
    with pytest.raises(ValueError):
        l.post(E("x", OCT, [P("cash", "debit", 100), P("rev", "credit", 99)]))


def test_single_posting_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("x", OCT, [P("cash", "debit", 1)]))


def test_balanced_in_total_not_per_currency_raises():
    with pytest.raises(ValueError):
        Ledger().post(E("x", OCT, [P("a", "debit", 100, "USD"), P("b", "credit", 100, "BRL")]))


@pytest.mark.parametrize("amt", [0, -5])
def test_non_positive_raises(amt):
    with pytest.raises(ValueError):
        Ledger().post(E("x", OCT, [P("a", "debit", amt), P("b", "credit", amt)]))


def test_immutable():
    e = simple()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.id = "y"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 1


def test_reversal_nets_to_prior():
    l = Ledger()
    l.post(simple())
    l.post(E("r", OCT, [P("cash", "credit", 100), P("rev", "debit", 100)]))
    assert l.balance("cash", "USD") == 0 and l.balance("rev", "USD") == 0


def test_closed_period_refused_adjustment_in_open_period_ok():
    l = Ledger()
    l.post(simple())
    l.close_period(date(2026, 10, 31))
    with pytest.raises(PeriodClosedError):
        l.post(simple("late", date(2026, 10, 31)))
    l.post(simple("adj", date(2026, 11, 1)))
    assert l.balance("cash", "USD", as_of=date(2026, 10, 31)) == 100
    assert l.balance("cash", "USD") == 200


def test_same_external_ref_returns_first():
    l = Ledger()
    first = l.post(simple("a", amt=100))
    again = l.post(E("b", OCT, [P("cash", "debit", 5), P("rev", "credit", 5)], ref="a"))
    assert again is first and len(l.entries) == 1


def test_trial_balance():
    import random
    l = Ledger()
    for i in range(50):
        a = random.randint(1, 1000)
        l.post(simple(f"r{i}", amt=a))
    assert sum(l.balances().values()) == 0


def test_close_cannot_move_backwards():
    l = Ledger()
    l.close_period(date(2026, 10, 31))
    with pytest.raises(ValueError):
        l.close_period(date(2026, 9, 30))
