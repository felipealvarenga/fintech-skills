import re
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from event_store import EventStore, ReplayError  # noqa: E402


class SqliteDB:
    """Adapts the %s / now() dialect used by EventStore to sqlite."""

    def __init__(self):
        self.c = sqlite3.connect(":memory:")
        self.c.executescript("""
            CREATE TABLE webhook_events(id TEXT PRIMARY KEY, type TEXT, raw BLOB,
                received_at TEXT, status TEXT DEFAULT 'received', processed_at TEXT, error TEXT);
            CREATE TABLE webhook_replays(id INTEGER PRIMARY KEY, event_id TEXT, actor TEXT,
                reason TEXT, replayed_at TEXT, outcome TEXT, error TEXT);
        """)

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?").replace("now()", "datetime('now')")
        return self.c.execute(sql, params)


@pytest.fixture
def store():
    s = EventStore(SqliteDB())
    s.save("evt_1", "payment.captured", b"{}")
    return s


def audit(store):
    return store.db.execute("SELECT actor, reason, outcome FROM webhook_replays").fetchall()


def test_replay_processes_and_audits(store):
    seen = []
    store.replay("evt_1", "ana", "handler bug fixed", lambda *a: seen.append(a))
    assert seen == [("evt_1", "payment.captured", b"{}")]
    assert store.get("evt_1")[3] == "processed"
    assert audit(store) == [("ana", "handler bug fixed", "processed")]


def test_failed_handler_marks_failed_then_replay_succeeds(store):
    def boom(*a):
        raise RuntimeError("bug")
    with pytest.raises(RuntimeError):
        store.replay("evt_1", "ana", "try", boom)
    assert store.get("evt_1")[3] == "failed"
    result = store.replay_failed("ana", "after fix", lambda *a: None)
    assert result == {"processed": ["evt_1"], "failed": []}
    assert store.get("evt_1")[3] == "processed"


def test_requires_actor_and_reason(store):
    with pytest.raises(ReplayError):
        store.replay("evt_1", "", "why", lambda *a: None)
    with pytest.raises(ReplayError):
        store.replay("evt_1", "ana", " ", lambda *a: None)
    assert audit(store) == []


def test_unknown_event(store):
    with pytest.raises(ReplayError):
        store.replay("nope", "ana", "why", lambda *a: None)


def test_concurrent_replay_refused(store):
    store.db.execute("UPDATE webhook_events SET status='processing' WHERE id=%s", ("evt_1",))
    with pytest.raises(ReplayError):
        store.replay("evt_1", "ana", "why", lambda *a: None)
