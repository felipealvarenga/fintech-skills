import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import limits_api


class FakeDB:
    """Minimal transactional fake: staged changes apply on commit only."""
    def __init__(self, limit=100, fail_audit=False):
        self.limit, self.events = limit, []
        self.fail_audit = fail_audit
        self._limit, self._events = limit, []

    def execute(self, sql, params=()):
        self._cur = None
        if sql.startswith("SELECT transfer_limit"):
            self._cur = [(self._limit,)]
        elif sql.startswith("UPDATE customers"):
            self._limit = params[0]
        elif "INSERT INTO audit_events" in sql:
            if self.fail_audit:
                raise RuntimeError("audit down")
            seq = len(self.events) + len(self._events) + 1
            self._events.append({"event_id": params[0], "sequence": seq, "actor_type": params[3],
                                 "actor_id": params[4], "on_behalf_of": params[5],
                                 "before": json.loads(params[6]), "after": json.loads(params[7]),
                                 "reason_code": params[8], "request_id": params[10]})
        return self

    def fetchone(self):
        return self._cur[0] if self._cur else None

    def commit(self):
        self.limit = self._limit
        self.events += self._events
        self._events = []

    def rollback(self):
        self._limit, self._events = self.limit, []


KW = dict(actor_id="admin1", reason_code="risk_review", request_id="req-1")


def test_success_writes_one_event_with_delta():
    db = FakeDB(100)
    limits_api.set_transfer_limit(db, "c1", 500, **KW)
    assert db.limit == 500 and len(db.events) == 1
    e = db.events[0]
    assert e["before"] == {"transfer_limit": 100} and e["after"] == {"transfer_limit": 500}
    assert e["request_id"] == "req-1" and e["actor_id"] == "admin1" and e["sequence"] == 1


def test_sequence_increments():
    db = FakeDB(100)
    limits_api.set_transfer_limit(db, "c1", 200, **KW)
    limits_api.set_transfer_limit(db, "c1", 300, **KW)
    assert [e["sequence"] for e in db.events] == [1, 2]


def test_failed_event_write_rolls_back_mutation():
    db = FakeDB(100, fail_audit=True)
    with pytest.raises(RuntimeError):
        limits_api.set_transfer_limit(db, "c1", 500, **KW)
    assert db.limit == 100 and db.events == []


def test_invalid_reason_writes_nothing():
    db = FakeDB(100)
    with pytest.raises(ValueError):
        limits_api.set_transfer_limit(db, "c1", 500, actor_id="a", reason_code="x", request_id="r")
    assert db.limit == 100 and db.events == []


def test_publish_failure_does_not_affect_commit():
    db = FakeDB(100)
    def boom(_): raise RuntimeError("queue down")
    limits_api.set_transfer_limit(db, "c1", 500, publish=boom, **KW)
    assert db.limit == 500 and len(db.events) == 1


def test_agent_actor_recorded():
    db = FakeDB(100)
    limits_api.set_transfer_limit(db, "c1", 500, actor_type="agent", on_behalf_of="cust-9", **KW)
    assert db.events[0]["actor_type"] == "agent" and db.events[0]["on_behalf_of"] == "cust-9"

# Still needed against a real DB (not covered by this fake): app role cannot UPDATE/DELETE
# audit_events, and concurrent writers produce gapless sequences.
