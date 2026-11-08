import random
from datetime import date
from reconcile import reconcile, _match_tiers, Config

D = date(2026, 5, 4)


def L(i, amt, ref="", d=D, cur="BRL"):
    return dict(id=i, date=d, amount_minor=amt, currency=cur, reference=ref)


def test_reference_beats_date():
    o = [L("o1", 100, "r2")]
    t = [L("t1", 100, "r1"), L("t2", 100, "r2")]
    m, _, _ = _match_tiers(o, t, Config(), "x")
    assert m[0]["theirs"] == "t2" and m[0]["rule"] == "x_tier1"


def test_window():
    o = [L("o", 5)]
    assert _match_tiers(o, [L("t", 5, d=date(2026, 5, 6))], Config(), "x")[0]
    assert not _match_tiers(o, [L("t", 5, d=date(2026, 5, 7))], Config(), "x")[0]


def test_duplicates_one_to_one():
    o = [L("o1", 5), L("o2", 5)]
    t = [L("t1", 5), L("t2", 5)]
    m, uo, ut = _match_tiers(o, t, Config(), "x")
    assert len(m) == 2 and not uo and not ut
    assert len({x["theirs"] for x in m}) == 2


def test_currency_mismatch():
    assert not _match_tiers([L("o", 5)], [L("t", 5, cur="USD")], Config(), "x")[0]


def test_shuffle_deterministic():
    o = [L(f"o{i}", 5, d=date(2026, 5, 4 + i % 2)) for i in range(6)]
    t = [L(f"t{i}", 5, d=date(2026, 5, 4 + i % 2)) for i in range(6)]
    a = _match_tiers(o, t, Config(), "x")[0]
    random.shuffle(o); random.shuffle(t)
    assert a == _match_tiers(o, t, Config(), "x")[0]


def S(i, amt, typ, ref=""):
    return dict(L(i, amt, ref), type=typ)


def test_payout_net_of_fees():
    ledger = [L("p1", 10000, "a")]
    stripe = [S("c1", 10000, "charge", "a"), S("f1", -300, "fee"), S("po", -9700, "payout")]
    bank = [dict(L("b1", 9700), description="STRIPE PAYOUT")]
    r = reconcile(ledger, stripe, bank)
    assert any(m["rule"] == "payout_net_of_fees" for m in r["matches"])
    assert r["fee_lines_to_book"][0]["amount_minor"] == -300
    assert not r["breaks"]


def test_payout_mismatch_is_break():
    stripe = [S("c1", 10000, "charge", "a"), S("po", -9700, "payout")]
    r = reconcile([L("p1", 10000, "a")], stripe, [])
    assert any(b["reason"] == "unknown" for b in r["breaks"])
