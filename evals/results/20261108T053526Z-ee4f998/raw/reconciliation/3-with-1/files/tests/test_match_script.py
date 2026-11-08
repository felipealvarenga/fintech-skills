import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from match_script import Config, reconcile  # noqa: E402


def L(id, d, amt, cur="USD", ref="", payout_ref="", kind=""):
    return {"id": id, "date": date.fromisoformat(d), "amount_minor": amt, "currency": cur,
            "reference": ref, "payout_ref": payout_ref, "kind": kind, "raw": {"id": id}}


def pairs(r):
    return {(m["ours"], m["theirs"]): m["tier"] for m in r.matches}


def test_reference_beats_date():
    ours = [L("o1", "2026-10-01", 100, ref="R1")]
    theirs = [L("t1", "2026-10-01", 100), L("t2", "2026-10-09", 100, ref="R1")]
    assert pairs(reconcile(ours, theirs)) == {("o1", "t2"): 1}


def test_date_window():
    c = Config(window_days=2)
    assert reconcile([L("o", "2026-10-01", 5)], [L("t", "2026-10-03", 5)], c).matches
    assert not reconcile([L("o", "2026-10-01", 5)], [L("t", "2026-10-04", 5)], c).matches


def test_duplicates_one_to_one():
    ours = [L("o1", "2026-10-01", 5), L("o2", "2026-10-01", 5)]
    theirs = [L("t1", "2026-10-01", 5), L("t2", "2026-10-01", 5)]
    r = reconcile(ours, theirs)
    assert len(r.matches) == 2
    assert len({m["theirs"] for m in r.matches}) == 2


def test_currency_mismatch():
    assert not reconcile([L("o", "2026-10-01", 5, "USD")], [L("t", "2026-10-01", 5, "EUR")]).matches


def test_shuffled_same_result():
    ours = [L(f"o{i}", "2026-10-01", i % 3) for i in range(9)]
    theirs = [L(f"t{i}", "2026-10-02", i % 3) for i in range(8)]
    a = reconcile(ours, theirs)
    random.Random(1).shuffle(ours)
    random.Random(2).shuffle(theirs)
    b = reconcile(ours, theirs)
    assert a.matches == b.matches and a.breaks == b.breaks


def test_nothing_lost_or_doubled():
    ours = [L("o1", "2026-10-01", 5), L("o2", "2026-10-01", 7)]
    theirs = [L("t1", "2026-10-01", 5), L("t2", "2026-10-01", 9)]
    r = reconcile(ours, theirs)
    seen = [m["theirs"] for m in r.matches] + [b["line_id"] for b in r.breaks if b["side"] == "theirs"]
    assert sorted(seen) == ["t1", "t2"]
    seen = [m["ours"] for m in r.matches] + [b["line_id"] for b in r.breaks if b["side"] == "ours"]
    assert sorted(seen) == ["o1", "o2"]


def test_fee_netting_tier3():
    ours = [L("c1", "2026-10-01", 1000, payout_ref="P1"),
            L("c2", "2026-10-01", 500, payout_ref="P1"),
            L("f1", "2026-10-01", -45, payout_ref="P1", kind="fee")]
    theirs = [L("p1", "2026-10-03", 1455, ref="P1")]
    r = reconcile(ours, theirs)
    assert len(r.matches) == 3 and all(m["rule"] == "payout_equals_captures_plus_fees" for m in r.matches)
    assert not r.breaks


def test_breaks_only_propose_adjustments():
    r = reconcile([L("o1", "2026-10-01", 5)], [])
    assert r.breaks[0]["owner"] and r.breaks[0]["reason"] == "missing_theirs"
    adj = r.proposed_adjustments[0]
    assert adj["break_id"] == r.breaks[0]["id"]
    assert adj["status"] == "proposed" and adj["requires_approval"]
