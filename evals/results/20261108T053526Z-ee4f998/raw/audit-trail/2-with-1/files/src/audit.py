"""Append-only audit store (SQLite reference implementation) with per-object sequence and hash chain."""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_event (
  event_id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  action TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  on_behalf_of TEXT,
  before TEXT,
  after TEXT,
  reason TEXT NOT NULL,
  request_id TEXT,
  idempotency_key TEXT,
  external_ref TEXT,
  policy_id TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  source TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL,
  UNIQUE (object_type, object_id, sequence)
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_event
BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_event
BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
"""

FIELDS = ("event_id", "object_type", "object_id", "sequence", "action", "actor_type",
          "actor_id", "on_behalf_of", "before", "after", "reason", "request_id",
          "idempotency_key", "external_ref", "policy_id", "occurred_at", "recorded_at", "source")


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class AuditStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        conn.executescript(SCHEMA)

    def append(self, *, object_type, object_id, action, actor_type, actor_id, reason,
               source, on_behalf_of=None, before=None, after=None, request_id=None,
               idempotency_key=None, external_ref=None, policy_id=None, occurred_at=None):
        """Insert one event in its own transaction. Raises on failure; callers must not proceed."""
        with self.conn:  # commit or rollback
            self.conn.execute("BEGIN IMMEDIATE") if not self.conn.in_transaction else None
            row = self.conn.execute(
                "SELECT sequence, hash FROM audit_event WHERE object_type=? AND object_id=? "
                "ORDER BY sequence DESC LIMIT 1", (object_type, object_id)).fetchone()
            seq, prev = (row[0] + 1, row[1]) if row else (1, "0" * 64)
            ev = {
                "event_id": str(uuid.uuid4()), "object_type": object_type,
                "object_id": object_id, "sequence": seq, "action": action,
                "actor_type": actor_type, "actor_id": actor_id, "on_behalf_of": on_behalf_of,
                "before": json.dumps(before, sort_keys=True), "after": json.dumps(after, sort_keys=True),
                "reason": reason, "request_id": request_id, "idempotency_key": idempotency_key,
                "external_ref": external_ref, "policy_id": policy_id,
                "occurred_at": occurred_at or utcnow(), "recorded_at": utcnow(), "source": source,
            }
            digest = hashlib.sha256(
                (prev + json.dumps(ev, sort_keys=True)).encode()).hexdigest()
            self.conn.execute(
                f"INSERT INTO audit_event ({','.join(FIELDS)},prev_hash,hash) "
                f"VALUES ({','.join('?' * (len(FIELDS) + 2))})",
                [ev[f] for f in FIELDS] + [prev, digest])
        return ev

    def events(self, object_type, object_id):
        cur = self.conn.execute(
            "SELECT " + ",".join(FIELDS) + " FROM audit_event WHERE object_type=? AND object_id=? "
            "ORDER BY sequence", (object_type, object_id))
        return [dict(zip(FIELDS, r)) for r in cur]

    def export_jsonl(self, object_type, object_id):
        return "\n".join(json.dumps({"schema_version": 1, **e}, sort_keys=True)
                         for e in self.events(object_type, object_id))

    def verify_chain(self, object_type, object_id):
        prev = "0" * 64
        rows = self.conn.execute(
            "SELECT " + ",".join(FIELDS) + ",prev_hash,hash FROM audit_event "
            "WHERE object_type=? AND object_id=? ORDER BY sequence", (object_type, object_id))
        for r in rows:
            ev = dict(zip(FIELDS, r[:-2]))
            if r[-2] != prev or hashlib.sha256((prev + json.dumps(ev, sort_keys=True)).encode()).hexdigest() != r[-1]:
                return False
            prev = r[-1]
        return True
