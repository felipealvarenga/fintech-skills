import dataclasses
import random
from datetime import date

import pytest

from capture import post_card_capture
from ledger import CREDIT, DEBIT, Ledger, LedgerError, Posting

T = "t1"
D = date(2026, 11, 1)


def P(acct, side, amt, cur="USD"):
    return Posting(acct, side, amt, cur)


def test_card_capture_100_fee_2_90_keep_5():
    l = Ledger()
    post_card_capture(l, T, "ch_1", D, 10000, 290, 500)
    assert l.balance(T, "1020") == 9710   # receivable, not cash
    assert l.balance(T, "1010") == 0
    assert l.balance(T, "5010") == 290
    assert l.balance(T, "2010") == 9500   # owed to merchant
    assert l.balance(T, "4010") == 500
    assert l.trial_balance(T) == (10000, 10000)


def test_capture_replay_is_noop():
    l = Ledger()
    a = post_card_capture(l, T, "ch_1", D, 10000, 290, 500)
    b = post_card_capture(l, T, "ch_1", D, 10000, 290, 500)
    assert a is b and len(l.entries) == 1


def test_balanced_posts_unbalanced_raises_single_posting_raises():
    l = Ledger()
    l.post(T, "a", D, [P("1010", DEBIT, 5), P("4010", CREDIT, 5)])
    with pytest.raises(LedgerError):
        l.post(T, "b", D, [P("1010", DEBIT, 5), P("4010", CREDIT, 4)])
    with pytest.raises(LedgerError):
        l.post(T, "c", D, [P("1010", DEBIT, 5)])


def test_balanced_in_total_but_not_per_currency_raises():
    l = Ledger()
    with pytest.raises(LedgerError):
        l.post(T, "x", D, [P("1010", DEBIT, 5, "USD"), P("4010", CREDIT, 5, "BRL")])


@pytest.mark.parametrize("amt", [0, -1])
def test_non_positive_amounts_raise(amt):
    with pytest.raises(LedgerError):
        P("1010", DEBIT, amt)


def test_immutable_after_posting():
    l = Ledger()
    e = l.post(T, "a", D, [P("1010", DEBIT, 5), P("4010", CREDIT, 5)])
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.external_ref = "z"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 99
    with pytest.raises(TypeError):
        e.postings[0] = P("1010", DEBIT, 1)
    assert isinstance(l.entries, tuple)


def test_reversal_nets_to_prior_balances():
    l = Ledger()
    post_card_capture(l, T, "ch_1", D, 10000, 290, 500)
    before = {a: l.balance(T, a) for a in l.chart}
    post_card_capture(l, T, "ch_2", D, 5000, 175, 250)
    l.reverse(T, "capture:ch_2", "rev:ch_2", D)
    assert {a: l.balance(T, a) for a in l.chart} == before


def test_closed_period():
    l = Ledger()
    l.post(T, "a", D, [P("1010", DEBIT, 5), P("4010", CREDIT, 5)])
    l.close_period(T, date(2026, 11, 30))
    with pytest.raises(LedgerError):
        l.post(T, "b", date(2026, 11, 30), [P("1010", DEBIT, 5), P("4010", CREDIT, 5)])
    l.reverse(T, "a", "rev:a", date(2026, 12, 1))  # adjustment in open period
    assert l.balance(T, "1010") == 0


def test_same_ref_returns_first_and_writes_nothing():
    l = Ledger()
    a = l.post(T, "a", D, [P("1010", DEBIT, 5), P("4010", CREDIT, 5)])
    b = l.post(T, "a", D, [P("1010", DEBIT, 9), P("4010", CREDIT, 9)])
    assert a is b and len(l.entries) == 1 and l.balance(T, "1010") == 5


def test_trial_balance_random_entries():
    rng = random.Random(1)
    l = Ledger()
    accts = list(l.chart)
    for i in range(200):
        amt = rng.randint(1, 10**6)
        l.post(T, f"r{i}", D, [P(rng.choice(accts), DEBIT, amt), P(rng.choice(accts), CREDIT, amt)])
    d, c = l.trial_balance(T)
    assert d == c > 0


def test_tenant_isolation():
    l = Ledger()
    post_card_capture(l, "t1", "ch_1", D, 10000, 290, 500)
    assert l.balance("t2", "2010") == 0
    assert l.trial_balance("t2") == (0, 0)
    post_card_capture(l, "t2", "ch_1", D, 100, 3, 5)  # same ref, different tenant
    assert l.balance("t1", "2010") == 9500
