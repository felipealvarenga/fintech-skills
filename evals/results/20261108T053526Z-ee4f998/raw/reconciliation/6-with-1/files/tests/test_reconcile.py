import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reconcile import Config, Line, load_ledger, load_stripe, reconcile  # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "src"


def L(id, d, amt, ref="", cur="BRL", type="capture", source="ledger"):
    return Line(source, id, date(2026, 5, d), amt, cur, ref, type)


def S(id, d, amt, ref="", cur="BRL", type="charge"):
    return L(id, d, amt, ref, cur, type, "stripe")


def pairs(r, tier=None):
    return sorted((tuple(m["ours"]), tuple(m["theirs"])) for m in r.matches
                  if tier is None or m["tier"] == tier)


def test_reference_beats_date():
    ours = [L("o1", 4, 100, "ch_x")]
    theirs = [S("t_date", 4, 100), S("t_ref", 5, 100, "ch_x")]
    r = reconcile(ours, theirs)
    assert pairs(r, 1) == [(("o1",), ("t_ref",))]


def test_date_window():
    cfg = Config(date_window_days=2)
    assert pairs(reconcile([L("o", 4, 100)], [S("t", 6, 100)], cfg), 2)
    assert not pairs(reconcile([L("o", 4, 100)], [S("t", 7, 100)], cfg))


def test_duplicate_amounts_one_to_one():
    r = reconcile([L("o1", 4, 100), L("o2", 4, 100)], [S("t1", 4, 100), S("t2", 4, 100)])
    assert len(pairs(r, 2)) == 2
    assert len({m["theirs"][0] for m in r.matches}) == 2


def test_currency_mismatch_never_matches():
    r = reconcile([L("o", 4, 100, "r")], [S("t", 4, 100, "r", cur="USD")])
    assert not r.matches


def test_shuffled_input_same_result():
    ours = load_ledger(SRC / "ledger.csv")
    theirs = load_stripe(SRC / "stripe_payout.csv")
    base = reconcile(ours, theirs)
    for seed in range(5):
        a, b = ours[:], theirs[:]
        random.Random(seed).shuffle(a)
        random.Random(seed).shuffle(b)
        r = reconcile(a, b)
        assert r.matches == base.matches and r.breaks == base.breaks


def test_every_id_once_nothing_lost():
    ours = load_ledger(SRC / "ledger.csv")
    theirs = load_stripe(SRC / "stripe_payout.csv")
    r = reconcile(ours, theirs)
    seen_o = [i for m in r.matches for i in m["ours"]] + [b["id"] for b in r.breaks if b["side"] == "ours"]
    seen_t = [i for m in r.matches for i in m["theirs"]] + [b["id"] for b in r.breaks if b["side"] == "theirs"]
    assert sorted(seen_o) == sorted(l.id for l in ours)
    assert sorted(seen_t) == sorted(l.id for l in theirs)


def test_payout_nets_fees_named_tier3():
    r = reconcile(load_ledger(SRC / "ledger.csv"), load_stripe(SRC / "stripe_payout.csv"))
    (m,) = [m for m in r.matches if m["tier"] == 3]
    assert m["rule"] == "payout_nets_fees"
    assert m["theirs"] == ["po_1", "txn_1", "txn_2", "txn_3", "txn_4", "txn_5"]
    assert m["ours"] == ["pay_1", "pay_2", "pay_3", "pay_5"]
    # pay_4 (ch_a4, 99900) is not in this payout: reported, not forced
    assert [b["id"] for b in r.breaks] == ["pay_4"]


def test_payout_that_does_not_net_is_unknown_break():
    theirs = [S("c", 4, 100, "r"), S("po", 5, -90, type="payout")]
    r = reconcile([L("o", 4, 100, "r")], theirs)
    assert [(b["id"], b["reason"], b["difference_minor"]) for b in r.breaks] == [("po", "unknown", 10)]
