import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from limits_api import Actor, AuditError, set_transfer_limit  # noqa: E402


class FakeDB:
    """Minimal in-memory stand-in with commit/rollback semantics."""

    def __init__(self, limit=1000, fail_insert=False):
        self.limit, self.committed_limit = limit, limit
        self.events, self.committed_events = [], []
        self.fail_insert = fail_insert
        self._row = None

    def execute(self, sql, params=()):
        if sql.startswith("SELECT transfer_limit"):
            self._row = (self.limit,)
        elif sql.startswith("SELECT sequence"):
            self._row = (self.events[-1]["sequence"], self.events[-1]["event_hash"]) if self.events else None
        elif sql.startswith("UPDATE customers"):
            self.limit = params[0]
        elif sql.startswith("INSERT INTO audit_events"):
            if self.fail_insert:
                raise RuntimeError("insert failed")
            self.events.append({"sequence": params[2], "event_hash": params[-1], "params": params})

    def fetchone(self):
        return self._row

    def commit(self):
        self.committed_limit, self.committed_events = self.limit, list(self.events)

    def rollback(self):
        self.limit, self.events = self.committed_limit, list(self.committed_events)


ADMIN = Actor("user", "admin-1")


def call(db, new=5000, **kw):
    args = dict(actor=ADMIN, reason_code="risk_review", reason_text="TICKET-1", request_id="req-1")
    args.update(kw)
    return set_transfer_limit(db, "c1", new, **args)


def test_success_writes_one_event_with_before_after():
    db = FakeDB()
    call(db)
    assert db.limit == 5000 and len(db.events) == 1
    p = db.events[0]["params"]
    assert '"transfer_limit_minor":1000' in p[6] and '"transfer_limit_minor":5000' in p[7]
    assert "req-1" in p


def test_sequence_and_hash_chain():
    db = FakeDB()
    call(db, 2000)
    call(db, 3000, request_id="req-2")
    assert [e["sequence"] for e in db.events] == [1, 2]
    assert db.events[1]["params"][-2] == db.events[0]["event_hash"]


def test_failed_event_write_rolls_back_limit():
    db = FakeDB(fail_insert=True)
    with pytest.raises(RuntimeError):
        call(db)
    assert db.limit == 1000 and db.events == []


def test_validation_failure_writes_nothing():
    db = FakeDB()
    with pytest.raises(AuditError):
        call(db, reason_code="because")
    with pytest.raises(AuditError):
        call(db, reason_text="")
    assert db.limit == 1000 and db.events == []


def test_agent_requires_on_behalf_of():
    with pytest.raises(AuditError):
        call(FakeDB(), actor=Actor("agent", "bot-1"))
    db = FakeDB()
    call(db, actor=Actor("agent", "bot-1", on_behalf_of="cust-9"))
    assert "agent" in db.events[0]["params"] and "cust-9" in db.events[0]["params"]
