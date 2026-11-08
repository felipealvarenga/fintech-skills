import dataclasses
import random
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ledger import (CREDIT, DEBIT, Entry, Ledger, LedgerError, Posting,  # noqa: E402
                    card_capture)

D = date(2026, 11, 8)
T = "t1"


def capture(ref="ch_1"):
    return card_capture(T, ref, D, gross_minor=10000, processor_fee_minor=290,
                        our_share_minor=500)


def test_capture_balances():
    led = Ledger()
    led.post(capture())
    assert led.balance(T, "1020") == 9710
    assert led.balance(T, "5010") == 290
    assert led.balance(T, "2010") == 9500  # owed to merchant
    assert led.balance(T, "4010") == 500
    assert led.trial_balance(T) == (10000, 10000)


def test_unbalanced_and_single_posting_raise():
    led = Ledger()
    with pytest.raises(LedgerError):
        led.post(Entry(T, "a", D, (Posting("1010", DEBIT, 100), Posting("4010", CREDIT, 99))))
    with pytest.raises(LedgerError):
        led.post(Entry(T, "b", D, (Posting("1010", DEBIT, 100),)))


def test_balanced_in_total_but_not_per_currency_raises():
    led = Ledger()
    with pytest.raises(LedgerError):
        led.post(Entry(T, "c", D, (Posting("1010", DEBIT, 100, "USD"),
                                   Posting("4010", CREDIT, 100, "BRL"))))


@pytest.mark.parametrize("amt", [0, -5])
def test_non_positive_amount_raises(amt):
    with pytest.raises(LedgerError):
        Posting("1010", DEBIT, amt)


def test_immutable():
    led = Ledger()
    e = led.post(capture())
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.memo = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.postings[0].amount_minor = 1
    with pytest.raises(AttributeError):
        e.postings.append(None)


def test_reversal_nets_to_zero():
    led = Ledger()
    led.post(capture())
    led.reverse(T, "ch_1", D)
    for acct in ("1020", "5010", "2010", "4010"):
        assert led.balance(T, acct) == 0


def test_closed_period_and_adjustment():
    led = Ledger(closed_through=date(2026, 10, 31))
    with pytest.raises(LedgerError):
        led.post(Entry(T, "old", date(2026, 10, 31), capture().postings))
    led.post(Entry(T, "adj", D, capture().postings, reverses=None))


def test_idempotent_reference():
    led = Ledger()
    first = led.post(capture())
    again = led.post(capture())
    assert again is first
    assert len(led.entries) == 1


def test_tenant_isolation():
    led = Ledger()
    led.post(capture())
    assert led.balance("other", "2010") == 0
    led.post(card_capture("other", "ch_1", D, gross_minor=100, processor_fee_minor=3,
                          our_share_minor=1))
    assert led.balance(T, "2010") == 9500


def test_trial_balance_random():
    rng = random.Random(1)
    led = Ledger()
    accts = ["1010", "1020", "2010", "4010", "5010"]
    for i in range(200):
        amt = rng.randint(1, 10_000)
        a, b = rng.sample(accts, 2)
        led.post(Entry(T, f"r{i}", D, (Posting(a, DEBIT, amt), Posting(b, CREDIT, amt))))
    d, c = led.trial_balance()
    assert d == c
