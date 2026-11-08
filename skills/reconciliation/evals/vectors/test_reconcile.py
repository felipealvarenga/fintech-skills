"""Test vectors for reconciliation.

Run against the reference: `pytest skills/reconciliation`.
Run against your module:   `RECON_SOLUTION=/path/to/reconcile.py pytest skills/reconciliation`.

The module under test must expose Line(id, date, amount, currency, reference=None, description="")
and reconcile(ours, theirs, date_window_days=2) returning an object with matches (each having
ours_id, theirs_id, tier), unmatched_ours and unmatched_theirs (lists of ids).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import random
from datetime import date, timedelta
from pathlib import Path


def _load():
    path = os.environ.get("RECON_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("recon_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
D = date(2026, 5, 4)


def L(id, amount, days=0, ref=None, ccy="BRL"):
    return m.Line(id, D + timedelta(days=days), amount, ccy, ref)


def pairs(result):
    return {(x.ours_id, x.theirs_id) for x in result.matches}


def test_reference_match_beats_date_match():
    ours = [L("o1", 1000, 0, "ref-A"), L("o2", 1000, 0, "ref-B")]
    theirs = [L("t1", 1000, 1, "ref-B"), L("t2", 1000, 0, "ref-A")]
    r = m.reconcile(ours, theirs)
    assert pairs(r) == {("o1", "t2"), ("o2", "t1")}
    assert all(x.tier == "reference" for x in r.matches)


def test_date_window_inside_and_outside():
    ours = [L("o1", 500)]
    assert pairs(m.reconcile(ours, [L("t1", 500, 2)])) == {("o1", "t1")}
    r = m.reconcile(ours, [L("t1", 500, 3)])
    assert pairs(r) == set()
    assert r.unmatched_ours == ["o1"] and r.unmatched_theirs == ["t1"]


def test_duplicates_match_one_to_one():
    ours = [L("o1", 700), L("o2", 700)]
    theirs = [L("t1", 700), L("t2", 700)]
    r = m.reconcile(ours, theirs)
    assert len(r.matches) == 2
    assert len({x.ours_id for x in r.matches}) == 2
    assert len({x.theirs_id for x in r.matches}) == 2
    assert r.unmatched_ours == [] and r.unmatched_theirs == []


def test_three_ours_two_theirs_leaves_one_break():
    ours = [L("o1", 700), L("o2", 700), L("o3", 700)]
    theirs = [L("t1", 700), L("t2", 700)]
    r = m.reconcile(ours, theirs)
    assert len(r.matches) == 2
    assert len(r.unmatched_ours) == 1
    assert r.unmatched_theirs == []


def test_currency_mismatch_never_matches():
    r = m.reconcile([L("o1", 1000, 0, "x", "USD")], [L("t1", 1000, 0, "x", "BRL")])
    assert pairs(r) == set()


def test_amount_mismatch_never_matches():
    r = m.reconcile([L("o1", 1000, 0, "x")], [L("t1", 1001, 0, "x")])
    assert pairs(r) == set()


def test_deterministic_under_shuffle_and_nothing_lost():
    rng = random.Random(11)
    ours, theirs = [], []
    for i in range(150):
        amt = rng.choice([100, 250, 999, 1234, 5000])
        d = rng.randint(0, 10)
        ref = f"r{i}" if rng.random() < 0.5 else None
        ours.append(L(f"o{i}", amt, d, ref))
        if rng.random() < 0.8:
            theirs.append(L(f"t{i}", amt, d + rng.randint(-3, 3), ref if rng.random() < 0.7 else None))
    for _ in range(5):
        theirs.append(L(f"tx{_}", 77, 0))
    base = m.reconcile(ours, theirs)
    for seed in range(5):
        o2, t2 = list(ours), list(theirs)
        random.Random(seed).shuffle(o2)
        random.Random(seed + 100).shuffle(t2)
        again = m.reconcile(o2, t2)
        assert pairs(again) == pairs(base)
        assert sorted(again.unmatched_ours) == sorted(base.unmatched_ours)
        assert sorted(again.unmatched_theirs) == sorted(base.unmatched_theirs)
    ours_ids = [x.ours_id for x in base.matches] + list(base.unmatched_ours)
    theirs_ids = [x.theirs_id for x in base.matches] + list(base.unmatched_theirs)
    assert sorted(ours_ids) == sorted(o.id for o in ours)
    assert sorted(theirs_ids) == sorted(t.id for t in theirs)


def test_reference_tier_does_not_match_different_amount():
    r = m.reconcile([L("o1", 1000, 0, "same")], [L("t1", 900, 0, "same")])
    assert pairs(r) == set()
    assert r.unmatched_ours == ["o1"] and r.unmatched_theirs == ["t1"]
