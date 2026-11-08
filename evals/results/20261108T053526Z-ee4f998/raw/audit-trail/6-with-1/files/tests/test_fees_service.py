"""Tests for fee audit trail. UNRUN: need a Postgres test DB fixture `db` (psycopg-style,
with `transaction()`), the migration applied, a fee 'f1' with bps=100, and `app_db`
connected as the application role."""
import pytest
from src.fees_service import update_fee

KW = dict(actor_id="u1", reason_code="pricing_change", reason="TCK-1", request_id="req-1")


def events(db, fee_id="f1"):
    return db.execute(
        "SELECT sequence, actor_id, before, after, reason_code, request_id "
        "FROM fee_audit_events WHERE object_id = %s ORDER BY sequence", (fee_id,)).fetchall()


def test_update_writes_columns_and_one_event(db):
    update_fee(db, "f1", 150, **KW)
    by, at = db.execute("SELECT updated_by, updated_at FROM fees WHERE id='f1'").fetchone()
    assert by == "u1" and at is not None
    evs = events(db)
    assert len(evs) == 1
    assert evs[0] == (1, "u1", {"bps": 100}, {"bps": 150}, "pricing_change", "req-1")


def test_sequence_gapless(db):
    update_fee(db, "f1", 150, **KW)
    update_fee(db, "f1", 200, **KW)
    assert [e[0] for e in events(db)] == [1, 2]


def test_failed_mutation_writes_no_event(db):
    with pytest.raises(LookupError):
        update_fee(db, "missing", 150, **KW)
    with pytest.raises(ValueError):
        update_fee(db, "f1", 150, **{**KW, "reason_code": "bogus"})
    assert events(db, "missing") == [] and events(db) == []


def test_failed_event_write_rolls_back(db, monkeypatch):
    db.execute("ALTER TABLE fee_audit_events ADD CONSTRAINT boom CHECK (false) NOT VALID")
    with pytest.raises(Exception):
        update_fee(db, "f1", 150, **KW)
    assert db.execute("SELECT bps FROM fees WHERE id='f1'").fetchone()[0] == 100


def test_app_role_cannot_update_or_delete_events(app_db):
    with pytest.raises(Exception):
        app_db.execute("UPDATE fee_audit_events SET reason = 'x'")
    with pytest.raises(Exception):
        app_db.execute("DELETE FROM fee_audit_events")


def test_agent_action_records_on_behalf_of(db):
    update_fee(db, "f1", 150, **{**KW, "actor_id": "agent-7"}, actor_type="agent", on_behalf_of="u1")
    row = db.execute("SELECT actor_type, on_behalf_of FROM fee_audit_events").fetchone()
    assert row == ("agent", "u1")
