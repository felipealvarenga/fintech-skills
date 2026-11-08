import sys
from datetime import date
from types import SimpleNamespace as NS

sys.path.insert(0, "src")
import qbo_sync as s

DAY = date(2026, 11, 7)


class FakeDB:
    def __init__(self, total=10050, mapped=True, state=None):
        self.total, self.state, self.executed = total, state, []
        self.accounts = [NS(key="sales", qbo_account_id="41"), NS(key="undeposited_funds", qbo_account_id="7")] if mapped else []

    def query(self, sql, params=()):
        if "account_mappings" in sql: return self.accounts
        if "SUM(amount)" in sql: return [NS(total=self.total)]
        if "FROM sync_state" in sql: return [self.state] if self.state else []
        return []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))


class FakeQBO:
    def __init__(self, remote_token="0", closed=False):
        self.creates, self.updates, self.remote_token, self.closed = [], [], remote_token, closed

    def _maybe_closed(self, p):
        if self.closed and p["TxnDate"] == DAY.isoformat():
            raise s.ClosedPeriodError()

    def create_journal_entry(self, p, rid):
        self._maybe_closed(p); self.creates.append((p, rid)); return {"Id": "99", "SyncToken": "0"}

    def update_journal_entry(self, p, rid):
        self._maybe_closed(p); self.updates.append((p, rid)); return {"Id": "99", "SyncToken": "1"}

    def get_journal_entry(self, i): return {"Id": i, "SyncToken": self.remote_token}
    def first_open_date(self, after): return date(2026, 11, 8)


def synced(db, qbo_total=10050, token="0"):
    accounts = {"sales": "41", "undeposited_funds": "7"}
    h = s.payload_hash(s.build_payload(DAY, qbo_total, accounts))
    return NS(qbo_id="99", sync_token=token, last_hash=h, status="synced")


def test_first_push_creates_with_requestid_and_major_units():
    q = FakeQBO()
    assert s.sync_day(FakeDB(), q, 1, DAY) == "created"
    p, rid = q.creates[0]
    assert p["Line"][0]["Amount"] == 100.5 and rid and len(rid) <= 36
    assert p["DocNumber"] == "SALES-2026-11-07"


def test_repeat_same_day_is_noop():
    q = FakeQBO()
    assert s.sync_day(FakeDB(state=synced(None)), q, 1, DAY) == "unchanged"
    assert not q.creates and not q.updates


def test_changed_total_updates_with_synctoken():
    q = FakeQBO()
    assert s.sync_day(FakeDB(total=20000, state=synced(None)), q, 1, DAY) == "updated"
    assert q.updates[0][0]["SyncToken"] == "0" and not q.creates


def test_stale_token_records_conflict_not_overwrite():
    q, db = FakeQBO(remote_token="3"), FakeDB(total=20000, state=synced(None))
    assert s.sync_day(db, q, 1, DAY) == "conflict"
    assert not q.updates and any("sync_conflicts" in e[0] for e in db.executed)


def test_closed_period_posts_in_open_period_with_original_date():
    q = FakeQBO(closed=True)
    assert s.sync_day(FakeDB(), q, 1, DAY) == "created"
    p, _ = q.creates[0]
    assert p["TxnDate"] == "2026-11-08" and "2026-11-07" in p["PrivateNote"]


def test_unmapped_posts_nothing_and_queues():
    q, db = FakeQBO(), FakeDB(mapped=False)
    assert s.sync_day(db, q, 1, DAY) == "unmapped"
    assert not q.creates and any("unmapped_queue" in e[0] for e in db.executed)


def test_rate_limit_defers():
    q = FakeQBO()
    q.create_journal_entry = lambda p, r: (_ for _ in ()).throw(s.RateLimitError("429"))
    assert s.sync_day(FakeDB(), q, 1, DAY) == "deferred"
