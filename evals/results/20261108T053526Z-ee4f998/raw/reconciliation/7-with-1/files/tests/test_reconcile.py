import random
from datetime import date

from recon.models import Config, Line
from recon.reconcile import reconcile

CFG = Config(as_of=date(2026, 11, 9), window_business_days=2)  # a Monday


def L(src, id, d, amt, ref="", cur="USD", **kw):
    return Line(src, id, d, amt, cur, ref, **kw)


def O(*a, **k): return L("ledger", *a, **k)
def T(*a, **k): return L("processor", *a, **k)


def pairs(r):
    return sorted((m.tier, m.ours, m.theirs) for m in r.matches)


def test_reference_beats_date_match():
    ours = [O("o1", date(2026, 11, 2), 1000, "A"), O("o2", date(2026, 11, 3), 1000, "B")]
    theirs = [T("t1", date(2026, 11, 3), 1000, "B")]
    r = reconcile(ours, theirs, CFG)
    assert pairs(r) == [("tier1_reference", ("o2",), ("t1",))]  # not o1, though o1 is earlier


def test_date_window_inside_and_outside():
    # Mon 2 Nov vs Wed 4 Nov = 2 business days: inside. Thu 5 Nov = 3: outside.
    inside = reconcile([O("o", date(2026, 11, 2), 500)], [T("t", date(2026, 11, 4), 500)], CFG)
    outside = reconcile([O("o", date(2026, 11, 2), 500)], [T("t", date(2026, 11, 5), 500)], CFG)
    assert pairs(inside) == [("tier2_date_window", ("o",), ("t",))]
    assert outside.matches == ()


def test_duplicate_amounts_match_two_not_one():
    ours = [O("o1", date(2026, 11, 2), 700), O("o2", date(2026, 11, 2), 700)]
    theirs = [T("t1", date(2026, 11, 2), 700), T("t2", date(2026, 11, 2), 700)]
    r = reconcile(ours, theirs, CFG)
    assert len(r.matches) == 2
    ids = [i for m in r.matches for i in m.ours]
    assert sorted(ids) == ["o1", "o2"]


def test_currency_mismatch_never_matches():
    r = reconcile([O("o", date(2026, 11, 2), 900, "R", cur="USD")],
                  [T("t", date(2026, 11, 2), 900, "R", cur="EUR")], CFG)
    assert r.matches == ()
    assert {b.reason for b in r.breaks} == {"fx"}


def test_shuffled_input_same_result():
    rnd = random.Random(1)
    ours = [O(f"o{i}", date(2026, 11, 2 + i % 3), 100 * (i % 4 + 1), f"R{i % 5}") for i in range(20)]
    theirs = [T(f"t{i}", date(2026, 11, 2 + i % 4), 100 * (i % 4 + 1), f"R{i % 6}") for i in range(20)]
    base = reconcile(ours, theirs, CFG)
    for _ in range(5):
        rnd.shuffle(ours); rnd.shuffle(theirs)
        r = reconcile(ours, theirs, CFG)
        assert r.matches == base.matches and r.breaks == base.breaks


def test_each_id_appears_once_and_nothing_lost():
    ours = [O(f"o{i}", date(2026, 11, 2), 100 * (i % 3 + 1), "R" if i < 2 else "") for i in range(8)]
    theirs = [T(f"t{i}", date(2026, 11, 3), 100 * (i % 3 + 1), "R" if i < 2 else "") for i in range(6)]
    r = reconcile(ours, theirs, CFG)
    seen = [i for m in r.matches for i in (*m.ours, *m.theirs)] + [b.line_id for b in r.breaks]
    assert len(seen) == len(set(seen))
    assert set(seen) == {l.id for l in ours + theirs}


def test_fee_nets_payout_in_named_tier3_rule():
    d = date(2026, 11, 2)
    ours = [O("c1", d, 10000, group="P1"), O("c2", d, 5000, group="P1")]
    theirs = [T("p1", d, 14550, kind="payout", group="P1"), T("f1", d, 450, kind="fee", group="P1")]
    r = reconcile(ours, theirs, CFG)
    assert len(r.matches) == 1
    m = r.matches[0]
    assert m.tier == "tier3:payout_gross_minus_fees"
    assert set(m.ours) == {"c1", "c2"} and set(m.theirs) == {"p1", "f1"}
    assert r.breaks == ()


def test_payout_that_does_not_net_is_not_force_matched():
    d = date(2026, 11, 2)
    ours = [O("c1", d, 10000, group="P1")]
    theirs = [T("p1", d, 9000, kind="payout", group="P1"), T("f1", d, 450, kind="fee", group="P1")]
    r = reconcile(ours, theirs, CFG)
    assert r.matches == ()
    assert {b.line_id for b in r.breaks} == {"c1", "p1", "f1"}


def test_break_reasons_owners_and_unknown_pages():
    ours = [O("o_new", date(2026, 11, 6), 100, "N"),       # recent: timing
            O("o_old", date(2026, 10, 20), 200, "X")]       # same ref, different amount: unknown
    theirs = [T("t_x", date(2026, 10, 20), 250, "X")]
    r = reconcile(ours, theirs, CFG)
    by = {b.line_id: b for b in r.breaks}
    assert by["o_new"].reason == "timing"
    assert by["o_old"].reason == "unknown" and by["o_old"].owner == "finance-on-call"
    assert any(a.startswith("PAGE") for a in r.alerts)
    assert r.metrics["unknown_amount_minor"] == 450
    assert r.metrics["oldest_open_break_days"] == 20


def test_reconcile_does_not_mutate_inputs():
    ours = [O("o", date(2026, 11, 2), 1)]
    theirs = [T("t", date(2026, 11, 2), 1)]
    reconcile(ours, theirs, CFG)
    assert len(ours) == 1 and len(theirs) == 1
