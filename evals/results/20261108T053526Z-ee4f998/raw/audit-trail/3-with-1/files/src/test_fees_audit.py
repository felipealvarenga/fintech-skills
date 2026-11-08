"""Tests for fee audit events. UNRUN: needs a Postgres fixture `db` (with fees and
audit_events tables) and a `db_app_role` fixture connected as the application role."""
import json
import pytest
from fees_service import update_fee

KW = dict(actor_type="user", actor_id="u_1", reason_code="pricing_review",
          reason="TICKET-123", request_id="req_1")


def events(db, fee_id):
    return db.execute("SELECT sequence, actor_id, before, after, reason_code, request_id "
                      "FROM audit_events WHERE object_id=%s ORDER BY sequence", (fee_id,)).fetchall()


def test_update_writes_one_event_with_delta(db):
    update_fee(db, "f_12", 275, **KW)
    ev = events(db, "f_12")
    assert len(ev) == 1
    seq, actor, before, after, code, req = ev[0]
    assert (seq, actor, code, req) == (1, "u_1", "pricing_review", "req_1")
    assert json.loads(after) == {"bps": 275} and "bps" in json.loads(before)


def test_sequence_gapless(db):
    for bps in (250, 260, 275):
        update_fee(db, "f_12", bps, **KW)
    assert [e[0] for e in events(db, "f_12")] == [1, 2, 3]


def test_missing_reason_rejected_and_no_event(db):
    with pytest.raises(ValueError):
        update_fee(db, "f_12", 300, **{**KW, "reason": " "})
    with pytest.raises(ValueError):
        update_fee(db, "f_12", 300, **{**KW, "reason_code": "because"})
    assert events(db, "f_12") == []


def test_failed_event_write_rolls_back_fee(db, break_audit_table):
    before = db.execute("SELECT bps FROM fees WHERE id='f_12'").fetchone()[0]
    with pytest.raises(Exception):
        update_fee(db, "f_12", 999, **KW)
    assert db.execute("SELECT bps FROM fees WHERE id='f_12'").fetchone()[0] == before


def test_app_role_cannot_update_or_delete_events(db, db_app_role):
    update_fee(db, "f_12", 275, **KW)
    for sql in ("UPDATE audit_events SET actor_id='x'", "DELETE FROM audit_events"):
        with pytest.raises(Exception):
            db_app_role.execute(sql)


def test_agent_action_records_on_behalf_of(db):
    update_fee(db, "f_12", 275, **{**KW, "actor_type": "agent", "actor_id": "agent_7"},
               on_behalf_of="u_1", approver_id="u_2")
    row = db.execute("SELECT actor_type, on_behalf_of, approver_id FROM audit_events").fetchone()
    assert row == ("agent", "u_1", "u_2")
