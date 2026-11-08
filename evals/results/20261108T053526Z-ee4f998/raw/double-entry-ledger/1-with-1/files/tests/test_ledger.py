import dataclasses
import os
import random
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger import (CASH, CREDIT, DEBIT, REVENUE, InMemoryStore, Ledger, LedgerError, Posting)

D, C = DEBIT, CREDIT
W = "2010:u1"


def P(acct, side, amt, cur="BRL"):
    return Posting(acct, side, amt, cur)


def L(closed=None):
    return Ledger(InMemoryStore(closed))


def test_balanced_posts():
    l = L()
    l.post("r1", [P(CASH, D, 100), P(W, C, 100)])
    assert l.balance(W, "BRL") == 100 and l.balance(CASH, "BRL") == 100


def test_unbalanced_raises():
    with pytest.raises(LedgerError):
        L().post("r1", [P(CASH, D, 100), P(W, C, 90)])


def test_single_posting_raises():
    with pytest.raises(LedgerError):
        L().post("r1", [P(CASH, D, 100)])


def test_balanced_in_total_not_per_currency_raises():
    with pytest.raises(LedgerError):
        L().post("r1", [P(CASH, D, 100, "BRL"), P(W, C, 100, "USD")])


def test_multi_currency_balanced_passes():
    L().post("r1", [P(CASH, D, 100, "BRL"), P(W, C, 100, "BRL"),
                    P("1010", D, 5, "USD"), P("2010:u2", C, 5, "USD")])


@pytest.mark.parametrize("amt", [0, -5])
def test_non_positive_raises(amt):
    with pytest.raises(LedgerError):
        L().post("r1", [P(CASH, D, amt), P(W, C, amt)])


def test_entries_immutable():
    e, _ = L().post("r1", [P(CASH, D, 100), P(W, C, 100)])
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.external_ref = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 1
    with pytest.raises(TypeError):
        e.postings[0] = None


def test_reversal_nets_to_prior():
    l = L()
    l.post("top", [P(CASH, D, 100), P(W, C, 100)])
    l.post("pay", [P(W, D, 30), P(REVENUE, C, 30)])
    l.reverse("rev", "pay")
    assert l.balance(W, "BRL") == 100 and l.balance(REVENUE, "BRL") == 0


def test_closed_period():
    l = L(closed=date(2026, 1, 31))
    with pytest.raises(LedgerError):
        l.post("r1", [P(CASH, D, 1), P(W, C, 1)], effective_date=date(2026, 1, 31))
    l.post("r2", [P(CASH, D, 1), P(W, C, 1)], effective_date=date(2026, 2, 1))


def test_idempotent_ref():
    l = L()
    e1, c1 = l.post("r1", [P(CASH, D, 100), P(W, C, 100)])
    e2, c2 = l.post("r1", [P(CASH, D, 999), P(W, C, 999)])
    assert c1 and not c2 and e1 is e2 and l.balance(W, "BRL") == 100


def test_trial_balance_random():
    l = L()
    accts = [CASH, W, REVENUE, "2010:u2"]
    for i in range(200):
        a, b = random.sample(accts, 2)
        n = random.randint(1, 10_000)
        l.post(f"r{i}", [P(a, D, n), P(b, C, n)])
    d = sum(l.store.sums(a, "BRL", None)[0] for a in accts)
    c = sum(l.store.sums(a, "BRL", None)[1] for a in accts)
    assert d == c


# --- wallet.pay with a fake db for the users cache ---
class FakeDb:
    def __init__(self):
        self.bal = 0

    def execute(self, sql, params=()):
        if sql.startswith("UPDATE users SET balance_minor = balance_minor"):
            self.bal += params[0]
        return self


def test_pay_decrements_cache_once_and_blocks_overdraft():
    import wallet
    db, l = FakeDb(), L()
    wallet.top_up(db, "u1", 100, "t1", ledger=l)
    wallet.pay(db, "u1", 40, "o1", ledger=l)
    wallet.pay(db, "u1", 40, "o1", ledger=l)  # replay: no double decrement
    assert db.bal == 60 and l.balance(W, "BRL") == 60
    with pytest.raises(LedgerError):
        wallet.pay(db, "u1", 100, "o2", ledger=l)
