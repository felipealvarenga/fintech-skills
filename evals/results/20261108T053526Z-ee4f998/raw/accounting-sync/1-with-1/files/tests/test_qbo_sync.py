import sys, os
from datetime import date
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import qbo_sync as s

DAY = date(2026, 11, 7)


class FakeDB:
    def __init__(self):
        self.pairs, self.conflicts, self.tokens, self.unmapped = {}, [], None, []
    def get_pair(self, t, i): return self.pairs.get((t, i))
    def save_pair(self, t, i, **f): self.pairs[(t, i)] = f
    def save_conflict(self, t, i, ours, theirs, policy): self.conflicts.append((i, ours, theirs, policy))
    def save_tokens(self, t, a, r, e): self.tokens = (a, r, e)
    def queue_unmapped(self, *a): self.unmapped.append(a)


class FakeQBO:
    def __init__(self):
        self.entries, self.n, self.closed, self.requestids = {}, 0, False, set()
    def create_journal_entry(self, p, requestid):
        if self.closed and p["TxnDate"] == str(DAY):
            raise s.ClosedPeriodError()
        for e in self.entries.values():          # requestid replay returns original
            if e.get("_rid") == requestid:
                return e
        self.n += 1
        e = dict(p, Id=str(self.n), SyncToken="0", _rid=requestid)
        self.entries[e["Id"]] = e
        return e
    def update_journal_entry(self, p, requestid):
        e = self.entries[p["Id"]]
        if p["SyncToken"] != e["SyncToken"]:
            raise s.StaleTokenError()
        e.update(p, SyncToken=str(int(e["SyncToken"]) + 1))
        return e
    def get_journal_entry(self, i): return self.entries[i]
    def first_open_date(self, after): return date(2026, 11, 8)
    def void_invoice(self, i, tok): return {"Id": i, "SyncToken": str(int(tok) + 1)}


def push(db, q, cents=10050, policy="review"):
    return s.push_summary(db, q, "t1", DAY, "sales", cents, "10", "20", policy)


def test_same_day_twice_creates_one_and_updates_on_change():
    db, q = FakeDB(), FakeQBO()
    assert push(db, q) == "created"
    assert push(db, q) == "noop"
    assert len(q.entries) == 1
    assert push(db, q, cents=20000) == "updated"
    assert len(q.entries) == 1


def test_stale_token_makes_conflict_not_overwrite():
    db, q = FakeDB(), FakeQBO()
    push(db, q)
    q.entries["1"]["SyncToken"] = "5"  # accountant edited
    assert push(db, q, cents=999) == "conflict"
    assert db.conflicts and q.entries["1"]["Line"][0]["Amount"] == 100.5


@pytest.mark.parametrize("policy,status,amount", [
    ("ours", "updated_ours", 9.99), ("theirs", "kept_theirs", 100.5), ("review", "conflict", 100.5)])
def test_remote_edit_policies(policy, status, amount):
    db, q = FakeDB(), FakeQBO()
    push(db, q)
    q.entries["1"]["SyncToken"] = "5"
    assert push(db, q, cents=999, policy=policy) == status
    assert q.entries["1"]["Line"][0]["Amount"] == amount
    assert len(db.conflicts) == 1


def test_closed_period_posts_in_open_period_with_original_date():
    db, q = FakeDB(), FakeQBO()
    q.closed = True
    assert push(db, q) == "closed_period"
    e = list(q.entries.values())[0]
    assert e["TxnDate"] == "2026-11-08" and "2026-11-07" in e["PrivateNote"]


def test_refresh_persists_new_token_even_if_next_call_fails():
    db = FakeDB()
    class OAuth:
        def refresh(self, r): return {"access_token": "a", "refresh_token": "NEW",
                                      "x_refresh_token_expires_in": 100}
    s.refresh_tokens(db, OAuth(), "t1", "OLD")
    assert db.tokens[1] == "NEW"


def test_deleted_invoice_is_voided_and_linked():
    db, q = FakeDB(), FakeQBO()
    db.save_pair("t1", "INV-1", their_id="9", sync_token="2", hash="h", status="synced", error=None)
    assert s.mirror_deleted_invoice(db, q, "t1", "INV-1") == "voided"
    p = db.get_pair("t1", "INV-1")
    assert p["status"] == "voided" and p["voided_of"] == "INV-1" and p["their_id"] == "9"


def test_drift_flags_one_cent():
    r = s.drift_report({"10": 10000}, {"10": 10001})
    assert r and r[0]["diff_cents"] == -1
    assert s.drift_report({"10": 5}, {"10": 5}) == []
