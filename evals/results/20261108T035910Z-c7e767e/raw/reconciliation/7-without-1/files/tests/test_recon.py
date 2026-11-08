import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from recon.loader import load_csv
from recon.matcher import reconcile
from recon.models import Txn
from recon.report import render_html, summarize


def t(id, d, amt, ref="", desc=""):
    return Txn(id, date.fromisoformat(d), Decimal(amt), ref, desc)


def test_reference_match():
    r = reconcile([t("b1", "2026-01-01", "10.00", "INV1")], [t("l1", "2026-01-02", "10.00", "INV1")])
    assert [m.kind for m in r.matches] == ["reference"]


def test_amount_mismatch_flagged():
    r = reconcile([t("b1", "2026-01-01", "10.00", "INV1")], [t("l1", "2026-01-01", "9.50", "INV1")])
    assert r.matches[0].kind == "amount_mismatch"
    assert r.matches[0].difference == Decimal("0.50")


def test_fuzzy_within_window_only():
    r = reconcile([t("b1", "2026-01-01", "5.00")], [t("l1", "2026-01-03", "5.00")])
    assert r.matches[0].kind == "fuzzy"
    r = reconcile([t("b1", "2026-01-01", "5.00")], [t("l1", "2026-01-20", "5.00")])
    assert not r.matches and len(r.unmatched_bank) == 1 and len(r.unmatched_ledger) == 1


def test_one_to_one():
    r = reconcile(
        [t("b1", "2026-01-01", "5.00"), t("b2", "2026-01-01", "5.00")],
        [t("l1", "2026-01-01", "5.00")],
    )
    assert len(r.matches) == 1 and len(r.unmatched_bank) == 1


def test_summary_and_html_escaping(tmp_path):
    r = reconcile([t("b<1>", "2026-01-01", "7.00", "X", "<script>")], [])
    s = summarize(r)
    assert s["unmatched_bank"] == 1 and s["net_variance"] == Decimal("7.00")
    html = render_html(r)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_loader(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("id,date,amount,reference\n1,2026-01-01,1.10,inv\n")
    assert load_csv(p)[0].reference == "INV"
    p.write_text("id,date,amount\n")
    try:
        load_csv(p)
        assert False
    except ValueError:
        pass
