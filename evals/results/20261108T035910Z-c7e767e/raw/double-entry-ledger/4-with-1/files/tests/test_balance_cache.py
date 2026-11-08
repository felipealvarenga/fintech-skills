import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger_min import Entry, Ledger, Posting  # noqa: E402


def entry(i, postings):
    return Entry(f"e{i}", date(2026, 1, 1), tuple(postings), f"ref{i}")


def test_cache_matches_derived_after_random_entries():
    rnd = random.Random(1)
    led = Ledger()
    accts = ["1010", "1020", "2010", "4010"]
    for i in range(200):
        a, b = rnd.sample(accts, 2)
        cur = rnd.choice(["BRL", "USD"])
        amt = rnd.randint(1, 10_000)
        led.post(entry(i, [Posting(a, "debit", amt, cur), Posting(b, "credit", amt, cur)]))
    assert led.reconcile() == {}
    for a in accts:
        for cur in ("BRL", "USD"):
            assert led.balance(a, cur) == led.derive_balance(a, cur)


def test_unknown_account_is_zero():
    assert Ledger().balance("nope", "BRL") == 0


def test_reconcile_detects_drift_and_rebuild_fixes_it():
    led = Ledger()
    led.post(entry(1, [Posting("1010", "debit", 500, "BRL"), Posting("2010", "credit", 500, "BRL")]))
    led._balances[("1010", "BRL")] += 7
    assert led.reconcile() == {("1010", "BRL"): (507, 500)}
    led.rebuild_balances()
    assert led.reconcile() == {}
    assert led.balance("1010", "BRL") == 500
