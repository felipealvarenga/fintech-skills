import random

from match_script import reconcile, payout_net_of_fees


def L(id, amount, d="2026-05-04", cur="BRL", ref=""):
    return {"id": id, "date": d, "amount_minor": str(amount), "currency": cur, "reference": ref}


def pairs(r):
    return {(o, t) for o, t, _ in r["matches"]}


def test_reference_beats_date_match():
    ours = [L("o1", 100, ref="r2")]
    theirs = [L("t1", 100, ref="r1"), L("t2", 100, d="2026-05-09", ref="r2")]
    r = reconcile(ours, theirs)
    assert r["matches"] == [("o1", "t2", "reference")]


def test_date_window_edges():
    ours = [L("o1", 100, d="2026-05-04")]
    assert reconcile(ours, [L("t1", 100, d="2026-05-06")])["matches"]
    assert not reconcile(ours, [L("t1", 100, d="2026-05-07")])["matches"]


def test_identical_amounts_match_one_to_one():
    ours = [L("o1", 100, ref="a"), L("o2", 100, ref="b")]
    theirs = [L("t1", 100, ref="b"), L("t2", 100, ref="a")]
    assert pairs(reconcile(ours, theirs)) == {("o1", "t2"), ("o2", "t1")}
    # no references: still two distinct matches
    r = reconcile([L("o1", 100), L("o2", 100)], [L("t1", 100), L("t2", 100)])
    assert len({t for _, t, _ in r["matches"]}) == 2


def test_currency_mismatch_never_matches():
    r = reconcile([L("o1", 100, cur="BRL")], [L("t1", 100, cur="USD")])
    assert r["matches"] == []


def test_shuffled_input_same_result():
    ours = [L(f"o{i}", 100 + i % 3, d=f"2026-05-0{1 + i % 4}") for i in range(8)]
    theirs = [L(f"t{i}", 100 + i % 3, d=f"2026-05-0{1 + i % 4}") for i in range(8)]
    base = reconcile(ours, theirs)
    random.Random(1).shuffle(ours)
    random.Random(2).shuffle(theirs)
    assert reconcile(ours, theirs) == base


def test_nothing_lost_or_duplicated():
    ours = [L("o1", 100), L("o2", 100), L("o3", 5)]
    theirs = [L("t1", 100), L("t2", 7)]
    r = reconcile(ours, theirs)
    o_ids = [o for o, _, _ in r["matches"]] + r["unmatched_ours"]
    t_ids = [t for _, t, _ in r["matches"]] + r["unmatched_theirs"]
    assert sorted(o_ids) == ["o1", "o2", "o3"]
    assert sorted(t_ids) == ["t1", "t2"]


def test_payout_net_of_fees():
    theirs = [
        {**L("c1", 10000), "type": "charge"},
        {**L("c2", 25000), "type": "charge"},
        {**L("f1", -1450), "type": "fee"},
        {**L("po", -33550), "type": "payout"},
    ]
    assert payout_net_of_fees(theirs) == ("po", ["c1", "c2", "f1"], 0)
