"""Audit tests for set_transfer_limit. UNRUN: written without a shell/DB available.

Uses an in-memory fake DB that emulates only the statements limits_api issues.
The privilege and concurrency tests need a real Postgres and are marked skip.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import limits_api  # noqa: E402


class _Cur:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class FakeDB:
    def __init__(self, limit=1000, fail_insert=False):
        self.limit = limit
        self.events = []
        self.fail_insert = fail_insert
        self._snap = None

    def execute(self, sql, params=()):
        if self._snap is None:
            self._snap = (self.limit, list(self.events))
        if sql.startswith("SELECT transfer_limit"):
            return _Cur((self.limit,))
        if sql.startswith("SELECT sequence"):
            return _Cur((self.events[-1]["sequence"], self.events[-1]["event_hash"]) if self.events else None)
        if sql.startswith("UPDATE customers"):
            self.limit = params[0]
            return _Cur()
        if sql.startswith("INSERT INTO audit_events"):
            if self.fail_insert:
                raise RuntimeError("audit write failed")
            keys = ["event_id", "object_type", "object_id", "sequence", "action", "actor_type",
                    "actor_id", "on_behalf_of", "authorization_ref", "before", "after",
                    "reason_code", "reason_text", "request_id", "idempotency_key", "occurred_at",
                    "source", "prev_hash", "event_hash"]
            self.events.append(dict(zip(keys, params)))
            return _Cur()
        raise AssertionError(sql)

    def commit(self):
        self._snap = None

    def rollback(self):
        if self._snap:
            self.limit, self.events = self._snap[0], self._snap[1]
        self._snap = None


def call(db, **over):
    kw = dict(actor_type="user", actor_id="admin-1", reason_code="customer_request",
              reason_text="TICKET-42", request_id="req-1")
    kw.update(over)
    return limits_api.set_transfer_limit(db, "c1", 5000, **kw)


def test_success_writes_exactly_one_complete_event():
    db = FakeDB(limit=1000)
    call(db, idempotency_key="idem-1")
    assert db.limit == 5000 and len(db.events) == 1
    e = db.events[0]
    assert json.loads(e["before"]) == {"transfer_limit_minor": 1000}
    assert json.loads(e["after"]) == {"transfer_limit_minor": 5000}
    assert e["request_id"] == "req-1" and e["actor_id"] == "admin-1"
    assert e["reason_code"] == "customer_request" and e["sequence"] == 1
    assert e["idempotency_key"] == "idem-1" and e["event_hash"]


def test_sequence_and_hash_chain():
    db = FakeDB()
    call(db)
    call(db, request_id="req-2")
    a, b = db.events
    assert (a["sequence"], b["sequence"]) == (1, 2)
    assert b["prev_hash"] == a["event_hash"]


@pytest.mark.parametrize("over", [
    {"reason_code": "because"}, {"reason_text": ""}, {"request_id": ""},
    {"actor_type": "robot"}, {"actor_type": "agent"},
])
def test_rejected_call_writes_nothing(over):
    db = FakeDB(limit=1000)
    with pytest.raises(ValueError):
        call(db, **over)
    assert db.limit == 1000 and db.events == []


def test_negative_limit_rejected():
    db = FakeDB()
    with pytest.raises(ValueError):
        limits_api.set_transfer_limit(db, "c1", -1, actor_type="user", actor_id="a",
                                      reason_code="correction", reason_text="x", request_id="r")


def test_failed_event_write_rolls_back_limit():
    db = FakeDB(limit=1000, fail_insert=True)
    with pytest.raises(RuntimeError):
        call(db)
    assert db.limit == 1000 and db.events == []


def test_agent_action_records_dual_identity():
    db = FakeDB()
    call(db, actor_type="agent", actor_id="agent-7", on_behalf_of="ops-3",
         authorization_ref="policy-run-99")
    e = db.events[0]
    assert e["actor_type"] == "agent" and e["on_behalf_of"] == "ops-3"
    assert e["authorization_ref"] == "policy-run-99"


@pytest.mark.skip(reason="needs real Postgres with the app role")
def test_app_role_cannot_update_or_delete_events():
    ...


@pytest.mark.skip(reason="needs real Postgres with concurrent connections")
def test_concurrent_writers_get_gapless_sequence():
    ...
