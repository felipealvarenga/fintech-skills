import dataclasses
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger_min import Entry, Ledger, Posting  # noqa: E402

D = lambda a, c, n, cur="BRL": Posting(a, "debit", n, cur)  # noqa: E731
C = lambda a, n, cur="BRL": Posting(a, "credit", n, cur)  # noqa: E731

ACCTS = ["1020", "5010", "2010", "4010"]


def capture(eid="cap1", ref="pay_1", d=date(2026, 11, 1)):
    return Entry(eid, d, (
        Posting("1020", "debit", 9710, "BRL"),
        Posting("5010", "debit", 290, "BRL"),
        Posting("2010", "credit", 9500, "BRL"),
        Posting("4010", "credit", 500, "BRL"),
    ), ref)


def test_balanced_posts_unbalanced_raises_single_posting_raises():
    l = Ledger()
    l.post(capture())
    with pytest.raises(ValueError):
        l.post(Entry("x", date(2026, 11, 2), (Posting("a", "debit", 5, "BRL"), Posting("b", "credit", 4, "BRL")), "r2"))
    with pytest.raises(ValueError):
        l.post(Entry("y", date(2026, 11, 2), (Posting("a", "debit", 5, "BRL"),), "r3"))


def test_balance_per_currency():
    l = Ledger()
    with pytest.raises(ValueError):
        l.post(Entry("x", date(2026, 11, 2), (
            Posting("a", "debit", 5, "BRL"), Posting("b", "credit", 5, "USD")), "r"))


def test_nonpositive_amounts_raise():
    l = Ledger()
    for n in (0, -5):
        with pytest.raises(ValueError):
            l.post(Entry("x", date(2026, 11, 2), (
                Posting("a", "debit", n, "BRL"), Posting("b", "credit", n, "BRL")), f"r{n}"))


def test_immutable():
    e = Ledger().post(capture())
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.id = "z"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 1


def test_refund_nets_every_account_to_zero():
    l = Ledger()
    l.post(capture())
    r = l.refund("cap1", "ref1", date(2026, 11, 8), "re_1")
    assert r.reverses == "cap1"
    for a in ACCTS:
        assert l.balance(a, "BRL") == 0


def test_refund_is_idempotent_and_cannot_double_refund():
    l = Ledger()
    l.post(capture())
    first = l.refund("cap1", "ref1", date(2026, 11, 8), "re_1")
    assert l.refund("cap1", "ref1b", date(2026, 11, 8), "re_1") is first
    assert len(l.entries) == 2
    with pytest.raises(ValueError):
        l.refund("cap1", "ref2", date(2026, 11, 8), "re_2")


def test_refund_unknown_or_of_reversal_raises():
    l = Ledger()
    with pytest.raises(ValueError):
        l.refund("nope", "r", date(2026, 11, 8), "re")
    l.post(capture())
    rev = l.refund("cap1", "ref1", date(2026, 11, 8), "re_1")
    with pytest.raises(ValueError):
        l.refund(rev.id, "ref2", date(2026, 11, 9), "re_2")


def test_refund_into_closed_period_raises_open_period_succeeds():
    l = Ledger(closed_through=date(2026, 11, 7))
    l.post(capture(d=date(2026, 11, 8)))
    l = Ledger()
    l.post(capture(d=date(2026, 11, 1)))
    l.closed_through = date(2026, 11, 7)
    with pytest.raises(ValueError):
        l.refund("cap1", "ref1", date(2026, 11, 7), "re_1")
    l.refund("cap1", "ref1", date(2026, 11, 8), "re_1")
    assert l.balance("1020", "BRL") == 0


def test_same_external_ref_returns_first_and_writes_nothing():
    l = Ledger()
    a = l.post(capture())
    b = l.post(capture(eid="other"))
    assert a is b and len(l.entries) == 1


def test_trial_balance():
    import random
    l = Ledger()
    for i in range(50):
        n = random.randint(1, 10000)
        l.post(Entry(f"e{i}", date(2026, 11, 1), (
            Posting(random.choice(ACCTS), "debit", n, "BRL"),
            Posting(random.choice(ACCTS), "credit", n, "BRL")), f"ref{i}"))
    assert sum(l.balance(a, "BRL") for a in ACCTS) == 0
