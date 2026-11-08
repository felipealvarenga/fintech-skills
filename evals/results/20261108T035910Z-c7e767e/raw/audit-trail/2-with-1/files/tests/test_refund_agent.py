import contextlib
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from refund_agent import maybe_approve  # noqa: E402


class FakeAudit:
    def __init__(self, fail=False):
        self.events, self.fail = [], fail

    @contextlib.contextmanager
    def transaction(self):
        mark = len(self.events)
        try:
            yield
        except Exception:
            del self.events[mark:]
            raise

    def append(self, e):
        if self.fail:
            raise RuntimeError("audit down")
        e = dict(e, sequence=len(self.events) + 1)
        self.events.append(e)


class FakePayments:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def refund(self, pid, amount, idempotency_key=None):
        if self.fail:
            raise ValueError("boom")
        self.calls.append((pid, amount, idempotency_key))
        return "psp_123"


class FakeLLM:
    model_id = "m1"

    def __init__(self, d="approve"):
        self.d = d

    def decide(self, r):
        return SimpleNamespace(decision=self.d, rationale="damaged item")


R = lambda amt: SimpleNamespace(payment_id="p1", amount_minor=amt, customer_id="c1")
CTX = {"request_id": "req1", "idempotency_key": "idem1"}


def test_approval_and_execution_are_separate_linked_events():
    a, p = FakeAudit(), FakePayments()
    assert maybe_approve(R(4999), FakeLLM(), p, a, CTX) == "executed"
    approved, executed = a.events
    assert approved["action"] == "refund.approved"
    assert approved["actor_type"] == "agent" and approved["on_behalf_of"] == "c1"
    assert approved["reason"] == "damaged item" and approved["model_id"] == "m1"
    assert approved["before"] != approved["after"]
    assert executed["action"] == "refund.executed"
    assert executed["external_reference"] == "psp_123"
    assert [e["sequence"] for e in a.events] == [1, 2]
    assert all(e["request_id"] == "req1" and e["idempotency_key"] == "idem1" for e in a.events)
    assert p.calls == [("p1", 4999, "idem1")]


def test_audit_failure_blocks_refund():
    a, p = FakeAudit(fail=True), FakePayments()
    with pytest.raises(RuntimeError):
        maybe_approve(R(100), FakeLLM(), p, a, CTX)
    assert p.calls == []


def test_over_limit_escalated_no_refund():
    a, p = FakeAudit(), FakePayments()
    assert maybe_approve(R(5000), FakeLLM(), p, a, CTX) == "escalated"
    assert p.calls == [] and a.events[0]["action"] == "refund.escalated"


def test_model_declines_recorded():
    a, p = FakeAudit(), FakePayments()
    maybe_approve(R(100), FakeLLM("deny"), p, a, CTX)
    assert p.calls == [] and a.events[0]["action"] == "refund.not_approved"


def test_payment_failure_recorded():
    a = FakeAudit()
    with pytest.raises(ValueError):
        maybe_approve(R(100), FakeLLM(), FakePayments(fail=True), a, CTX)
    assert [e["action"] for e in a.events] == ["refund.approved", "refund.execution_failed"]
