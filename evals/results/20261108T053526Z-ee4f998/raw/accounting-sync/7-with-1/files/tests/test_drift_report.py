import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from qbo_sync import drift_report  # noqa: E402


class FakeDB:
    def __init__(self, payments, mappings):
        self.payments, self.mappings = payments, mappings

    def query(self, sql, params=()):
        return self.mappings if "account_mappings" in sql else self.payments


class FakeQBO:
    def __init__(self, pl):
        self.pl = pl

    def profit_and_loss(self, start, end):
        return self.pl


MAP = [NS(our_account="sales", qbo_account_id="79")]
PAYMENTS = [NS(id=1, amount=1000), NS(id=2, amount=550)]  # 15.50


def run(pl, mappings=MAP, **kw):
    return drift_report(FakeDB(PAYMENTS, mappings), FakeQBO(pl), "t1", "2026-11-01", "2026-11-07", **kw)


def test_matching_balances_have_no_drift():
    assert run({"79": "15.50"}) == {"drifts": [], "unmapped": []}


def test_planted_one_cent_difference_is_flagged():
    r = run({"79": "15.49"})
    assert r["drifts"][0]["diff_cents"] == 1


def test_threshold_allows_small_difference():
    assert run({"79": "15.49"}, threshold_cents=1)["drifts"] == []


def test_unmapped_account_is_reported_not_guessed():
    r = run({"79": "15.50"}, mappings=[])
    assert r["unmapped"][0]["our_account"] == "sales" and r["drifts"] == []


def test_task_opened_on_drift():
    seen = []
    run({"79": "0"}, open_task=lambda *a: seen.append(a))
    assert len(seen) == 1
