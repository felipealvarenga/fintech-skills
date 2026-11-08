"""Test vectors for audit-trail.

Run against the reference: `pytest skills/audit-trail`.
Run against your module:   `AUDIT_SOLUTION=/path/to/audit.py pytest skills/audit-trail`.

The module under test must expose AuditLog (append, events, verify_chain, query, export),
AuditError and mutate(state, object_type, object_id, change, log, **audit) as used below.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("AUDIT_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("audit_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
T0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def ticking_clock():
    t = {"now": T0}
    def clock():
        t["now"] += timedelta(seconds=1)
        return t["now"]
    return clock


def log():
    return m.AuditLog(clock=ticking_clock())


def test_mutation_writes_one_event_with_required_fields():
    L = log()
    state = {"cus_1": {"transfer_limit": 100_000}}
    m.mutate(state, "customer", "cus_1", {"transfer_limit": 250_000}, L,
             action="limit.change", actor_type="support", actor_id="emp_9", request_id="req_1",
             reason_code="customer_request", reason_text="ticket 4411")
    assert state["cus_1"]["transfer_limit"] == 250_000
    assert len(L.events) == 1
    e = L.events[0]
    assert e.before == {"transfer_limit": 100_000} and e.after == {"transfer_limit": 250_000}
    assert (e.actor_type, e.actor_id, e.reason_code, e.request_id, e.sequence) == ("support", "emp_9", "customer_request", "req_1", 1)
    assert e.occurred_at and e.recorded_at


def test_human_action_without_reason_rolls_back_the_change():
    L = log()
    state = {"cus_1": {"transfer_limit": 100_000}}
    with pytest.raises(m.AuditError):
        m.mutate(state, "customer", "cus_1", {"transfer_limit": 1}, L,
                 action="limit.change", actor_type="user", actor_id="u1", request_id="req_2")
    assert state["cus_1"]["transfer_limit"] == 100_000
    assert len(L.events) == 0


def test_events_are_append_only_and_immutable():
    L = log()
    e = L.append(object_type="fee", object_id="f1", action="create", actor_type="service", actor_id="billing",
                 request_id="r", after={"bps": 250})
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.after = {"bps": 1}  # type: ignore[misc]
    assert not hasattr(L, "update") and not hasattr(L, "delete")
    snapshot = L.events
    assert isinstance(snapshot, tuple)


def test_sequence_is_gapless_per_object_under_interleaving():
    L = log()
    for i in range(6):
        obj = "a" if i % 2 == 0 else "b"
        L.append(object_type="limit", object_id=obj, action="set", actor_type="system", actor_id="cron", request_id=f"r{i}")
    assert [e.sequence for e in L.query(object_id="a")] == [1, 2, 3]
    assert [e.sequence for e in L.query(object_id="b")] == [1, 2, 3]


def test_sensitive_fields_are_masked_in_before_and_after():
    L = log()
    e = L.append(object_type="customer", object_id="c", action="document.update", actor_type="support", actor_id="s",
                 request_id="r", reason_code="kyc", before={"cpf": "52998224725", "name": "Ana"},
                 after={"cpf": "11144477735", "name": "Ana"})
    assert e.before["cpf"] == "*********25" and e.after["cpf"] == "*********35"
    assert e.before["name"] == "Ana"


def test_agent_actions_record_both_identities_and_approval_is_separate():
    L = log()
    with pytest.raises(m.AuditError):
        L.append(object_type="refund", object_id="rf1", action="execute", actor_type="agent", actor_id="refund-bot", request_id="r1")
    approval = L.append(object_type="refund", object_id="rf1", action="approve", actor_type="agent", actor_id="refund-bot",
                        on_behalf_of="policy:auto-refund-under-50", request_id="r1", after={"amount": 4_900})
    execution = L.append(object_type="refund", object_id="rf1", action="execute", actor_type="service", actor_id="payments",
                         request_id="r1", after={"status": "sent"})
    assert approval.on_behalf_of == "policy:auto-refund-under-50"
    assert approval.sequence == 1 and execution.sequence == 2
    assert approval.actor_id != execution.actor_id


def test_unknown_actor_type_and_missing_request_id_are_refused():
    L = log()
    with pytest.raises(m.AuditError):
        L.append(object_type="x", object_id="1", action="a", actor_type="robot", actor_id="r", request_id="r")
    with pytest.raises(m.AuditError):
        L.append(object_type="x", object_id="1", action="a", actor_type="system", actor_id="s", request_id="")


def test_hash_chain_detects_tampering():
    L = log()
    for i in range(3):
        L.append(object_type="fee", object_id="f", action="set", actor_type="system", actor_id="s", request_id=f"r{i}", after={"bps": i})
    assert L.verify_chain() is True
    tampered = dataclasses.replace(L.events[1], after={"bps": 99})
    L._events[1] = tampered  # simulates a direct write to storage
    assert L.verify_chain() is False


def test_query_by_object_actor_and_time_and_export_schema():
    L = log()
    L.append(object_type="fee", object_id="f1", action="set", actor_type="user", actor_id="u1", request_id="r1", reason_code="pricing",
             occurred_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
    L.append(object_type="fee", object_id="f2", action="set", actor_type="user", actor_id="u2", request_id="r2", reason_code="pricing",
             occurred_at=datetime(2026, 8, 2, tzinfo=timezone.utc))
    L.append(object_type="limit", object_id="l1", action="set", actor_type="user", actor_id="u1", request_id="r3", reason_code="risk",
             occurred_at=datetime(2026, 9, 2, tzinfo=timezone.utc))
    q3 = L.query(object_type="fee", since="2026-07-01", until="2026-09-30T23:59:59+00:00")
    assert [e.object_id for e in q3] == ["f1", "f2"]
    assert [e.object_id for e in L.query(actor_id="u1")] == ["f1", "l1"]
    rows = L.export(q3)
    assert rows[0]["schema"] == "audit-export/1"
    assert {"object_id", "actor_id", "before", "after", "reason_code", "hash", "sequence"} <= set(rows[0])
