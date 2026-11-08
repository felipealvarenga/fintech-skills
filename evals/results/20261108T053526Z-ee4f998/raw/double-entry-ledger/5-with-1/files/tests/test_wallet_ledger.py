import random
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import wallet
from ledger import Ledger, LedgerError, Posting

D = date(2026, 11, 1)
RATE = Decimal("0.20")  # USD per BRL


@pytest.fixture
def L():
    ledger = Ledger()
    wallet.setup(ledger)
    return ledger


def test_balanced_posts_unbalanced_raises_single_posting_raises(L):
    L.post("a", [Posting("cash:USD", "debit", 5), Posting("merchant_payable:USD", "credit", 5)], D)
    with pytest.raises(LedgerError):
        L.post("b", [Posting("cash:USD", "debit", 5), Posting("merchant_payable:USD", "credit", 4)], D)
    with pytest.raises(LedgerError):
        L.post("c", [Posting("cash:USD", "debit", 5)], D)


def test_balanced_in_total_but_not_per_currency_raises(L):
    with pytest.raises(LedgerError):
        L.post("x", [Posting("cash:USD", "debit", 100), Posting("cash:BRL", "credit", 100)], D)


@pytest.mark.parametrize("amt", [0, -1])
def test_non_positive_amount_raises(L, amt):
    with pytest.raises(LedgerError):
        L.post("z", [Posting("cash:USD", "debit", amt), Posting("merchant_payable:USD", "credit", amt)], D)


def test_entries_immutable(L):
    e = wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    with pytest.raises(Exception):
        e.postings[0].amount_minor = 1
    with pytest.raises(Exception):
        e.external_ref = "other"
    assert isinstance(e.postings, tuple)


def test_brl_top_up_stores_usd_and_records_rate(L):
    e = wallet.top_up(L, "br1", 5000, "BRL", "t2", D, RATE)
    assert wallet.balance_usd(L, "br1") == 1000
    assert e.rate == RATE
    assert L.balance("cash:BRL") == 5000


def test_display_conversion_is_not_stored(L):
    wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    n = len(L.entries)
    assert wallet.balance_display(L, "u1", "BRL", RATE) == 5000
    assert len(L.entries) == n


def test_shared_wallet_us_and_br_pay(L):
    wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    wallet.pay(L, "u1", 2500, "BRL", "p1", D, RATE)
    assert wallet.balance_usd(L, "u1") == 500
    with pytest.raises(LedgerError):
        wallet.pay(L, "u1", 600, "USD", "p2", D)


def test_reversal_nets_to_prior_balance(L):
    wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    p = wallet.pay(L, "u1", 300, "USD", "p1", D)
    L.reverse(p.id, "p1-rev", D)
    assert wallet.balance_usd(L, "u1") == 1000


def test_closed_period_refused_adjustment_in_open_period_ok(L):
    wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    L.closed_through = D
    with pytest.raises(LedgerError):
        wallet.top_up(L, "u1", 1, "USD", "t2", D)
    wallet.top_up(L, "u1", 1, "USD", "t2", date(2026, 11, 2))


def test_same_reference_is_noop(L):
    a = wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    b = wallet.top_up(L, "u1", 1000, "USD", "t1", D)
    assert a is b and len(L.entries) == 1


def test_trial_balance_after_random_entries(L):
    rng = random.Random(1)
    for i in range(50):
        if rng.random() < 0.5:
            wallet.top_up(L, "u1", rng.randint(1, 9999), rng.choice(["USD", "BRL"]), f"t{i}", D, RATE)
        else:
            try:
                wallet.pay(L, "u1", rng.randint(1, 500), rng.choice(["USD", "BRL"]), f"p{i}", D, RATE)
            except LedgerError:
                pass
    for cur in ("USD", "BRL"):
        net = sum((p.amount_minor if p.side == "debit" else -p.amount_minor)
                  for e in L.entries for p in e.postings if L._accounts[p.account][0] == cur)
        assert net == 0
