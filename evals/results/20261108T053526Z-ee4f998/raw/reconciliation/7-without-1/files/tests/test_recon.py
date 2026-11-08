import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from recon import Transaction, reconcile
from recon.dashboard import render_html
from recon.loader import load_csv


def T(id, d, amt, ref="", desc=""):
    return Transaction(id, date.fromisoformat(d), Decimal(amt), ref, desc)


def test_exact_match():
    r = reconcile([T("L1", "2026-01-05", "100.00", "INV1")], [T("B1", "2026-01-05", "100.00", "INV1")])
    assert [m.kind for m in r.matched] == ["exact"]
    assert r.variance == 0 and r.match_rate == 1.0


def test_fuzzy_match_within_tolerance():
    r = reconcile([T("L1", "2026-01-05", "50.00")], [T("B1", "2026-01-07", "50.00")])
    assert r.matched[0].kind == "fuzzy"


def test_outside_tolerance_unmatched():
    r = reconcile([T("L1", "2026-01-05", "50.00")], [T("B1", "2026-01-20", "50.00")])
    assert len(r.unmatched_ledger) == 1 and len(r.unmatched_bank) == 1


def test_amount_mismatch_by_reference():
    r = reconcile([T("L1", "2026-01-05", "100.00", "INV9")], [T("B1", "2026-01-05", "90.00", "INV9")])
    assert len(r.amount_mismatches) == 1
    assert r.amount_mismatches[0].difference == Decimal("10.00")
    assert r.variance == Decimal("10.00")


def test_bank_row_used_once():
    r = reconcile(
        [T("L1", "2026-01-05", "10.00"), T("L2", "2026-01-05", "10.00")],
        [T("B1", "2026-01-05", "10.00")],
    )
    assert len(r.matched) == 1 and len(r.unmatched_ledger) == 1


def test_html_escapes_input():
    r = reconcile([T("L1", "2026-01-05", "1.00", desc="<script>x</script>")], [])
    html = render_html(r)
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_loader(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("id,date,amount,reference\nA,2026-01-01,\"1,234.50\",R\n")
    assert load_csv(f)[0].amount == Decimal("1234.50")


def test_loader_bad_row(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("id,date,amount\nA,notadate,1\n")
    with pytest.raises(ValueError, match="a.csv:2"):
        load_csv(f)
