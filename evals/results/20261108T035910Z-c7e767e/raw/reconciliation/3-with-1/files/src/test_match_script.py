import random
from match_script import month_end, normalize, reconcile


def L(src, id, amt, d="2026-10-01", ref="", cur="USD"):
    return normalize({"id": id, "amount_minor": amt, "date": d, "reference": ref, "currency": cur}, src)


def test_reference_beats_date():
    o = [L("o", "o1", 100, ref="R1")]
    t = [L("t", "t1", 100, ref=""), L("t", "t2", 100, ref="R1", d="2026-10-20")]
    m, _, _ = reconcile(o, t)
    assert m == [{"ours": "o1", "theirs": "t2", "tier": 1}]


def test_window():
    o = [L("o", "o1", 100)]
    assert reconcile(o, [L("t", "t1", 100, d="2026-10-03")])[0]
    assert not reconcile(o, [L("t", "t1", 100, d="2026-10-04")])[0]


def test_duplicates_one_to_one():
    o = [L("o", "o1", 100), L("o", "o2", 100)]
    t = [L("t", "t1", 100), L("t", "t2", 100)]
    m, uo, ut = reconcile(o, t)
    assert len(m) == 2 and not uo and not ut


def test_currency_mismatch():
    assert not reconcile([L("o", "o1", 100)], [L("t", "t1", 100, cur="EUR")])[0]


def test_shuffle_deterministic():
    o = [L("o", f"o{i}", 100 + i % 3) for i in range(9)]
    t = [L("t", f"t{i}", 100 + i % 3) for i in range(8)]
    a = reconcile(o, t)
    random.shuffle(o); random.shuffle(t)
    assert reconcile(o, t) == a


def test_month_end_proposes_but_never_posts():
    rec = month_end([{"id": "o1", "amount_minor": "500", "date": "2026-10-01"}], [], "2026-11-01T00:00Z")
    adj = rec["proposed_adjustments"][0]
    assert adj["status"] == "pending_approval" and adj["break_ref"] == "ours:o1"
