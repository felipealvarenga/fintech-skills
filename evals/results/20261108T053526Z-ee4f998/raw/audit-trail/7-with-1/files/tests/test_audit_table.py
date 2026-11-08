"""Audit table tests. Need Postgres with src/audit_table.sql and src/audit_verify.sql applied.
AUDIT_APP_DSN = role app; AUDIT_VERIFIER_DSN = role audit_verifier;
AUDIT_TAMPER_DSN = superuser, used only to simulate an attacker bypassing the guards.
"""
import os
import threading

import psycopg
import pytest

APP = os.environ.get("AUDIT_APP_DSN")
VER = os.environ.get("AUDIT_VERIFIER_DSN")
TAMPER = os.environ.get("AUDIT_TAMPER_DSN")
pytestmark = pytest.mark.skipif(not (APP and VER and TAMPER), reason="DSNs not set")

INSERT = """INSERT INTO audit_events
  (object_type, object_id, action, actor_type, actor_id, before, after, request_id, occurred_at)
  VALUES (%s, %s, 'limit.change', 'user', 'u1', '{"limit":1}', '{"limit":2}', 'req-1', now())"""


def add(obj, n=1):
    with psycopg.connect(APP, autocommit=True) as c:
        for _ in range(n):
            c.execute(INSERT, ("account", obj))


def test_app_cannot_update_or_delete_or_truncate():
    add("a1")
    with psycopg.connect(APP, autocommit=True) as c:
        for sql in ("UPDATE audit_events SET action='x'", "DELETE FROM audit_events",
                    "TRUNCATE audit_events"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql)


def test_even_superuser_update_is_blocked_by_trigger():
    add("a2")
    with psycopg.connect(TAMPER, autocommit=True) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("UPDATE audit_events SET action='x' WHERE object_id='a2'")


def test_sequence_gapless_for_concurrent_writers():
    ts = [threading.Thread(target=add, args=("a3", 10)) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with psycopg.connect(VER) as c:
        seqs = [r[0] for r in c.execute(
            "SELECT sequence FROM audit_events WHERE object_id='a3' ORDER BY sequence")]
    assert seqs == list(range(1, 51))


def test_clean_chain_has_no_violations():
    add("a4", 3)
    with psycopg.connect(VER) as c:
        assert c.execute("SELECT count(*) FROM audit_chain_violations").fetchone()[0] == 0


def _tamper(sql):
    with psycopg.connect(TAMPER, autocommit=True) as c:
        c.execute("ALTER TABLE audit_events DISABLE TRIGGER audit_events_no_update_delete")
        try:
            c.execute(sql)
        finally:
            c.execute("ALTER TABLE audit_events ENABLE TRIGGER audit_events_no_update_delete")


def test_detects_edited_row():
    add("a5", 2)
    _tamper("UPDATE audit_events SET after='{\"limit\":999}' WHERE object_id='a5' AND sequence=1")
    with psycopg.connect(VER) as c:
        rows = c.execute("SELECT problem FROM audit_chain_violations WHERE object_id='a5'").fetchall()
    assert ("content_modified",) in rows


def test_detects_deleted_middle_row():
    add("a6", 3)
    _tamper("DELETE FROM audit_events WHERE object_id='a6' AND sequence=2")
    with psycopg.connect(VER) as c:
        assert c.execute(
            "SELECT count(*) FROM audit_chain_violations WHERE object_id='a6'").fetchone()[0] >= 1


def test_detects_deleted_tail_via_digest():
    add("a7", 2)
    with psycopg.connect(VER, autocommit=True) as c:
        c.execute("SELECT audit_write_digest(current_date + 1000)")
    _tamper("DELETE FROM audit_events WHERE object_id='a7' AND sequence=2")
    with psycopg.connect(VER) as c:
        assert c.execute("SELECT count(*) FROM audit_digest_violations").fetchone()[0] >= 1
