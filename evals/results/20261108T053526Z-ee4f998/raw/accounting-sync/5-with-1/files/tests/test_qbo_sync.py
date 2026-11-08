import sys, pathlib
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
import qbo_sync

MAPPING = {"sales": "10", "undeposited": "20"}
DAY = date(2026, 10, 31)


class ClosedPeriodError(Exception):
    pass


class FakeState:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def save(self, k, **f):
        self.d.setdefault(k, {}).update(f)


class FakeQbo:
    ClosedPeriodError = ClosedPeriodError

    def __init__(self, closed_before=None):
        self.closed_before = closed_before
        self.calls = []

    def first_open_date(self, after):
        return date(2026, 11, 1)

    def create_journal_entry(self, payload, request_id=None):
        self.calls.append((payload, request_id))
        if self.closed_before and date.fromisoformat(payload["TxnDate"]) < self.closed_before:
            raise ClosedPeriodError()
        return {"Id": str(len(self.calls)), "SyncToken": "0"}


def test_closed_period_posts_in_open_period_once_with_original_date():
    qbo, st = FakeQbo(closed_before=date(2026, 11, 1)), FakeState()
    r = qbo_sync.push_day(qbo, st, "t1", DAY, 12345, MAPPING)
    assert r["status"] == "posted_open_period"
    assert len(qbo.calls) == 2  # one refused, one accepted: no retry loop
    payload = qbo.calls[-1][0]
    assert payload["TxnDate"] == "2026-11-01"
    assert "2026-10-31" in payload["PrivateNote"]


def test_same_day_pushed_twice_creates_one_entry():
    qbo, st = FakeQbo(), FakeState()
    qbo_sync.push_day(qbo, st, "t1", DAY, 500, MAPPING)
    qbo_sync.push_day(qbo, st, "t1", DAY, 500, MAPPING)
    assert len(qbo.calls) == 1


def test_changed_amount_is_flagged_not_duplicated():
    qbo, st = FakeQbo(), FakeState()
    qbo_sync.push_day(qbo, st, "t1", DAY, 500, MAPPING)
    r = qbo_sync.push_day(qbo, st, "t1", DAY, 600, MAPPING)
    assert len(qbo.calls) == 1 and r["status"] == "needs_update"


def test_unmapped_account_does_not_post():
    qbo, st = FakeQbo(), FakeState()
    try:
        qbo_sync.push_day(qbo, st, "t1", DAY, 500, {"sales": "10"})
        assert False
    except qbo_sync.UnmappedAccount:
        pass
    assert qbo.calls == []


def test_amount_converted_to_major_units():
    _, p = qbo_sync.build_entry("t1", DAY, 12345, MAPPING)
    assert p["Line"][0]["Amount"] == 123.45
