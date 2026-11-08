import random
import pytest
from match_script import Config, reconcile


def L(id, amt, d="2026-05-04", cur="BRL", ref="", **kw):
    return {"id": id, "date": d, "amount_minor": str(amt), "currency": cur, "reference": ref, **kw}


def pairs(r):
    return {(m["ours"], m["theirs"]): m["tier"] for m in r["matches"]}


def test_reference_beats_date():
    ours = [L("o1", 100, ref="r2"), L("o2", 100, ref="r1")]
    theirs = [L("t1", 100, ref="r1"), L("t2", 100, ref="r2")]
    p = pairs(reconcile(ours, theirs))
    assert p == {("o1", "t2"): "reference", ("o2", "t1"): "reference"}


def test_date_window():
    r = reconcile([L("o", 100)], [L("t", 100, d="2026-05-06")])
    assert pairs(r) == {("o", "t"): "amount_date"}
    r = reconcile([L("o", 100)], [L("t", 100, d="2026-05-07")])
    assert not r["matches"]


def test_duplicates_one_to_one():
    ours = [L("o1", 100), L("o2", 100)]
    theirs = [L("t1", 100), L("t2", 100)]
    assert len(reconcile(ours, theirs)["matches"]) == 2
    assert len(reconcile(ours, [L("t1", 100)])["matches"]) == 1


def test_currency_mismatch():
    assert not reconcile([L("o", 100)], [L("t", 100, cur="USD")])["matches"]


def test_shuffle_invariant():
    ours = [L(f"o{i}", 100 + i % 3, d=f"2026-05-0{1 + i % 3}") for i in range(9)]
    theirs = [L(f"t{i}", 100 + i % 3, d=f"2026-05-0{1 + i % 3}") for i in range(9)]
    base = reconcile(ours, theirs)
    for s in range(5):
        random.Random(s).shuffle(ours)
        random.Random(s).shuffle(theirs)
        assert reconcile(ours, theirs) == base


def test_nothing_lost_or_duplicated():
    ours = [L("o1", 100), L("o2", 200), L("o3", 300)]
    theirs = [L("t1", 100), L("t2", 999)]
    r = reconcile(ours, theirs)
    o = [m["ours"] for m in r["matches"]] + r["unmatched_ours"]
    t = [m["theirs"] for m in r["matches"]] + r["unmatched_theirs"]
    assert sorted(o) == ["o1", "o2", "o3"] and sorted(t) == ["t1", "t2"]


def test_fee_nets_payout():
    theirs = [L("c1", 1000, type="charge"), L("f1", -50, type="fee"), L("p1", -950, type="payout")]
    r = reconcile([], theirs)
    assert r["groups"][0]["rule"] == "payout_nets_captures_minus_fees"
    assert r["unmatched_theirs"] == ["c1"] or "c1" not in r["unmatched_theirs"]
    assert "p1" not in r["unmatched_theirs"]


def test_tolerance_off_by_default():
    assert not reconcile([L("o", 10000)], [L("t", 10150)])["matches"]


def test_tolerance_needs_reason():
    with pytest.raises(ValueError):
        Config(amount_tolerance_pct=0.02)


def test_tolerance_recorded():
    cfg = Config(amount_tolerance_pct=0.02, tolerance_reason="stripe FX rounding")
    m = reconcile([L("o", 10000)], [L("t", 10150)], cfg)["matches"][0]
    assert m["tier"] == "amount_tol" and m["diff_minor"] == 150 and m["tolerance_reason"]
    assert not reconcile([L("o", 10000)], [L("t", 10300)], cfg)["matches"]
