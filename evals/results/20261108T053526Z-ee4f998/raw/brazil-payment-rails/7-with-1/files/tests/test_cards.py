import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cards import build_receivable_schedule, record_sale  # noqa: E402


class FakeLedger:
    def __init__(self):
        self.receivables = []
        self.cash_in = []

    def post_receivable(self, **kw):
        self.receivables.append(kw)

    def post_cash_in(self, amount_minor):
        self.cash_in.append(amount_minor)


def test_10x_sale_creates_10_rows_summing_to_amount():
    ledger = FakeLedger()
    sale = SimpleNamespace(amount_minor=120000, installments=10, date=date(2026, 11, 8))
    schedule = record_sale(ledger, sale)
    assert len(schedule) == 10
    assert len(ledger.receivables) == 10
    assert sum(r["amount_minor"] for r in ledger.receivables) == 120000
    assert ledger.cash_in == []  # no cash at sale time


def test_remainder_centavos_are_not_lost():
    rows = build_receivable_schedule(100001, 10, date(2026, 11, 8))
    assert sum(r["amount_minor"] for r in rows) == 100001
    assert rows[0]["amount_minor"] == 10001
