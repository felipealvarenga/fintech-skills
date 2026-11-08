import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import capture_service as cs  # noqa: E402


class Db:
    """sqlite adapter accepting %s placeholders."""

    def __init__(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE payments (id TEXT PRIMARY KEY, status TEXT)")
        self.c.execute(
            "CREATE TABLE outbox (event_id TEXT PRIMARY KEY, topic TEXT, payload TEXT, published_at TIMESTAMP)"
        )
        self.c.execute("INSERT INTO payments VALUES ('p1', 'authorized')")
        self.c.commit()

    def execute(self, sql, params=()):
        return self.c.execute(sql.replace("%s", "?"), params)

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()


class Processor:
    def __init__(self, timeouts=0):
        self.calls = []
        self.timeouts = timeouts

    def capture(self, payment_id, idempotency_key):
        self.calls.append(idempotency_key)
        if self.timeouts:
            self.timeouts -= 1
            raise TimeoutError()


class Bus:
    def __init__(self):
        self.msgs = []

    def publish(self, topic, payload):
        self.msgs.append((topic, payload))


def status(db):
    return db.execute("SELECT status FROM payments WHERE id='p1'").fetchone()[0]


def test_capture_emits_event_once_via_outbox():
    db, bus = Db(), Bus()
    cs.capture(db, Processor(), "p1")
    assert status(db) == "captured"
    assert cs.publish_outbox(db, bus) == 1
    assert cs.publish_outbox(db, bus) == 0
    assert bus.msgs == [("payment.captured", {"payment_id": "p1", "event_id": "payment.captured:p1"})]


def test_second_capture_rejected_with_current_state():
    db, proc = Db(), Processor()
    cs.capture(db, proc, "p1")
    with pytest.raises(cs.InvalidState) as e:
        cs.capture(db, proc, "p1")
    assert e.value.status == "captured"
    assert len(proc.calls) == 1


def test_timeout_leaves_pending_and_no_event_then_retry_uses_same_key():
    db, bus, proc = Db(), Bus(), Processor(timeouts=1)
    with pytest.raises(TimeoutError):
        cs.capture(db, proc, "p1")
    assert status(db) == "capture_pending"
    assert cs.publish_outbox(db, bus) == 0
    cs.capture(db, proc, "p1")
    assert status(db) == "captured"
    assert proc.calls == ["capture:p1", "capture:p1"]
    assert cs.publish_outbox(db, bus) == 1


def test_bus_failure_does_not_lose_event():
    db = Db()
    cs.capture(db, Processor(), "p1")

    class Down:
        def publish(self, *a):
            raise ConnectionError()

    with pytest.raises(ConnectionError):
        cs.publish_outbox(db, Down())
    bus = Bus()
    assert cs.publish_outbox(db, bus) == 1
