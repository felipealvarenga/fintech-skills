import random
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from recon import Config, Line, reconcile  # noqa: E402
from recon.dashboard import render  # noqa: E402
from recon.store import load_run, save_run  # noqa: E402

CFG = Config(as_of=date(2026, 11, 6))  # a Friday


def L(src, id, d, amt, cur="USD", ref="", **raw):
    return Line(src, id, d, amt, cur, ref, "", raw)


def D(day):
    return date(2026, 11, day)


def test_reference_beats_date_match():
    ours = [L("o", "o1", D(2), 100, ref="R1")]
    theirs = [L("t", "t1", D(2), 100, ref="OTHER"), L("t", "t2", D(4), 100, ref="R1")]
    r = reconcile(ours, theirs, CFG)
    assert r.matches[0].theirs == ("t2",) and r.matches[0].tier == 1


def test_date_window_inside_and_outside():
    # Mon 2 -> Wed 4 = 2 business days (inside); Thu 5 = 3 (outside)
    inside = reconcile([L("o", "o1", D(2), 100)], [L("t", "t1", D(4), 100)], CFG)
    outside = reconcile([L("o", "o1", D(2), 100)], [L("t", "t1", D(5), 100)], CFG)
    assert len(inside.matches) == 1 and inside.matches[0].tier == 2
    assert not outside.matches and len(outside.breaks) == 2


def test_duplicates_match_one_to_one():
    ours = [L("o", "o1", D(2), 100), L("o", "o2", D(2), 100)]
    theirs = [L("t", "t1", D(2), 100), L("t", "t2", D(2), 100)]
    r = reconcile(ours, theirs, CFG)
    assert len(r.matches) == 2 and not r.breaks
    assert {m.theirs for m in r.matches} == {("t1",), ("t2",)}


def test_extra_duplicate_is_a_break_not_double_match():
    ours = [L("o", "o1", D(2), 100, ref="R")]
    theirs = [L("t", "t1", D(2), 100, ref="R"), L("t", "t2", D(2), 100, ref="R")]
    r = reconcile(ours, theirs, CFG)
    assert len(r.matches) == 1
    assert [(b.line_id, b.reason) for b in r.breaks] == [("t2", "duplicate")]


def test_currency_mismatch_never_matches():
    r = reconcile([L("o", "o1", D(2), 100, "USD", "R")], [L("t", "t1", D(2), 100, "EUR", "R")], CFG)
    assert not r.matches
    assert {b.reason for b in r.breaks} == {"fx"}


def test_shuffled_input_same_result():
    ours = [L("o", f"o{i}", D(2 + i % 3), 100 * (i % 4 + 1)) for i in range(12)]
    theirs = [L("t", f"t{i}", D(2 + i % 3), 100 * (i % 4 + 1)) for i in range(10)]
    base = reconcile(ours, theirs, CFG)
    for seed in range(5):
        a, b = ours[:], theirs[:]
        random.Random(seed).shuffle(a)
        random.Random(seed).shuffle(b)
        assert reconcile(a, b, CFG) == base


def test_no_line_lost_or_reused():
    ours = [L("o", f"o{i}", D(2), 100 + i % 3) for i in range(9)]
    theirs = [L("t", f"t{i}", D(3), 100 + i % 4) for i in range(7)]
    r = reconcile(ours, theirs, CFG)
    seen = [i for m in r.matches for i in (*m.ours, *m.theirs)] + [b.line_id for b in r.breaks]
    assert sorted(seen) == sorted([l.id for l in ours + theirs])


def test_payout_nets_captures_and_fee_tier3():
    ours = [L("o", "c1", D(2), 10000, ref="PO1"), L("o", "c2", D(2), 5000, ref="PO1"),
            L("o", "f1", D(2), -450, ref="PO1")]
    theirs = [L("t", "p1", D(4), 14550, ref="PO1", type="payout")]
    r = reconcile(ours, theirs, CFG)
    assert len(r.matches) == 1 and not r.breaks
    m = r.matches[0]
    assert m.tier == 3 and m.rule == "payout_equals_captures_minus_fees"
    assert set(m.ours) == {"c1", "c2", "f1"}


def test_unknown_old_break_pages_and_metrics():
    r = reconcile([], [L("t", "t1", D(2), 700, ref="X", type="mystery")], CFG)
    assert r.breaks[0].reason == "unknown"
    assert r.metrics["unknown_amount_minor"] == 700
    assert any(a.startswith("PAGE") for a in r.alerts)


def test_timing_break_for_recent_unmatched_ours():
    r = reconcile([L("o", "o1", D(5), 100)], [], CFG)
    assert r.breaks[0].reason == "timing"


def test_run_record_immutable_and_dashboard(tmp_path):
    ours, theirs = [L("o", "o1", D(2), 100)], [L("t", "t1", D(2), 100)]
    r = reconcile(ours, theirs, CFG)
    at = datetime(2026, 11, 6, 8, 0, 0)
    p = save_run(tmp_path, at, ours, theirs, CFG, r)
    try:
        save_run(tmp_path, at, ours, theirs, CFG, r)
        assert False, "overwrite allowed"
    except FileExistsError:
        pass
    html = render(load_run(p))
    assert "Match rate" in html and "100.0%" in html
