import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from ledger_min import Entry, Ledger, Posting  # noqa: E402

ACCTS = ["1020", "5010", "2010", "4010"]


def capture():
    return Entry("e1", date(2026, 11, 1), (
        Posting("1020", "debit", 9710, "BRL"),
        Posting("5010", "debit", 290, "BRL"),
        Posting("2010", "credit", 9500, "BRL"),
        Posting("4010", "credit", 500, "BRL"),
    ), "pay_1")


def test_refund_nets_to_zero_and_links_original():
    l = Ledger()
    l.post(capture())
    r = l.refund("pay_1", "refund_1", date(2026, 11, 8))
    assert r.reverses == "e1"
    for a in ACCTS:
        assert l.balance(a, "BRL") == 0


def test_refund_replay_is_noop():
    l = Ledger()
    l.post(capture())
    first = l.refund("pay_1", "refund_1", date(2026, 11, 8))
    assert l.refund("pay_1", "refund_1", date(2026, 11, 8)) is first
    assert len(l.entries) == 2


def test_double_refund_with_new_ref_raises():
    l = Ledger()
    l.post(capture())
    l.refund("pay_1", "refund_1", date(2026, 11, 8))
    with pytest.raises(ValueError):
        l.refund("pay_1", "refund_2", date(2026, 11, 8))


def test_refund_into_closed_period_raises_open_period_ok():
    l = Ledger()
    l.post(capture())
    l.closed_through = date(2026, 11, 7)
    with pytest.raises(ValueError):
        l.refund("pay_1", "refund_1", date(2026, 11, 5))
    l.refund("pay_1", "refund_1", date(2026, 11, 8))


def test_unknown_payment_raises():
    with pytest.raises(ValueError):
        Ledger().refund("nope", "r", date(2026, 11, 8))


def test_validation():
    l = Ledger()
    with pytest.raises(ValueError):
        l.post(Entry("x", date(2026, 11, 1), (Posting("a", "debit", 1, "BRL"),), "x"))
    with pytest.raises(ValueError):  # balanced in total, not per currency
        l.post(Entry("y", date(2026, 11, 1), (
            Posting("a", "debit", 1, "BRL"), Posting("b", "credit", 1, "USD")), "y"))
    with pytest.raises(ValueError):
        l.post(Entry("z", date(2026, 11, 1), (
            Posting("a", "debit", 0, "BRL"), Posting("b", "credit", 0, "BRL")), "z"))
