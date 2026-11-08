from decimal import Decimal
import pytest
from wallet import *

R = Decimal("0.18")  # USD per BRL


def test_brl_topup_stored_as_usd():
    l = Ledger()
    e = top_up(l, "u1", 10000, "BRL", "t1", R)  # R$100.00
    assert wallet_balance_usd(l, "u1") == 1800
    assert e.fx_rate == R


def test_us_and_br_share_wallet():
    l = Ledger()
    top_up(l, "u1", 1000, "USD", "t1")
    top_up(l, "u1", 10000, "BRL", "t2", R)
    pay(l, "u1", 5000, "BRL", "p1", R)  # R$50 = $9.00
    assert wallet_balance_usd(l, "u1") == 1000 + 1800 - 900


def test_insufficient_funds():
    l = Ledger()
    with pytest.raises(LedgerError):
        pay(l, "u1", 100, "USD", "p1")


def test_idempotent_ref():
    l = Ledger()
    top_up(l, "u1", 500, "USD", "t1")
    top_up(l, "u1", 500, "USD", "t1")
    assert wallet_balance_usd(l, "u1") == 500


def test_unbalanced_and_single_posting_raise():
    l = Ledger()
    with pytest.raises(LedgerError):
        l.post("x", [Posting("a", "debit", 1, "USD"), Posting("b", "credit", 2, "USD")])
    with pytest.raises(LedgerError):
        l.post("y", [Posting("a", "debit", 1, "USD")])


def test_balanced_in_total_not_per_currency_raises():
    l = Ledger()
    with pytest.raises(LedgerError):
        l.post("z", [Posting("a", "debit", 5, "USD"), Posting("b", "credit", 5, "BRL")])
