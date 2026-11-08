import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit import AuditStore  # noqa: E402
from refund_agent import maybe_approve  # noqa: E402


class LLM:
    model = "test-model"

    def __init__(self, out="approve"):
        self.out = out

    def decide(self, r):
        return self.out


class Pay:
    def __init__(self):
        self.calls = []

    def refund(self, pid, amt):
        self.calls.append((pid, amt))
        return SimpleNamespace(id="re_123")


def mk(amount=1000):
    return SimpleNamespace(id="r1", payment_id="p1", amount_minor=amount, customer_id="c1")


@pytest.fixture
def audit():
    return AuditStore(sqlite3.connect(":memory:", isolation_level=None))


def test_approved_refund_has_decision_and_execution_events(audit):
    pay = Pay()
    assert maybe_approve(mk(), LLM(), pay, audit, request_id="req1")
    evs = audit.events("refund", "r1")
    assert [e["action"] for e in evs] == ["agent_decision", "refund_executed"]
    assert [e["sequence"] for e in evs] == [1, 2]
    d, x = evs
    assert d["actor_type"] == "agent" and d["on_behalf_of"] == "c1" and d["request_id"] == "req1"
    assert d["policy_id"] and d["reason"] and d["before"] and d["after"]
    assert x["external_ref"] == "re_123" and x["idempotency_key"] == d["idempotency_key"]
    assert audit.verify_chain("refund", "r1")


def test_declined_and_over_threshold_move_no_money(audit):
    pay = Pay()
    assert not maybe_approve(mk(), LLM("deny"), pay, audit)
    assert not maybe_approve(mk(5000), LLM(), pay, audit)
    assert pay.calls == []
    assert [e["action"] for e in audit.events("refund", "r1")] == ["agent_decision", "escalated_to_human"]


def test_audit_failure_blocks_refund():
    class Broken:
        def append(self, **kw):
            raise RuntimeError("db down")

    pay = Pay()
    with pytest.raises(RuntimeError):
        maybe_approve(mk(), LLM(), pay, Broken())
    assert pay.calls == []


def test_events_are_append_only(audit):
    maybe_approve(mk(), LLM(), Pay(), audit)
    with pytest.raises(sqlite3.DatabaseError):
        audit.conn.execute("UPDATE audit_event SET reason='x'")
    with pytest.raises(sqlite3.DatabaseError):
        audit.conn.execute("DELETE FROM audit_event")


def test_export_has_schema_version(audit):
    maybe_approve(mk(), LLM(), Pay(), audit)
    assert '"schema_version": 1' in audit.export_jsonl("refund", "r1").splitlines()[0]
