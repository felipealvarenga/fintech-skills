"""Test vectors for idempotent-payments.

Run against the reference: `pytest skills/idempotent-payments`.
Run against your module:   `IDEMPOTENCY_SOLUTION=/path/to/payments.py pytest skills/idempotent-payments`.

The module under test must expose IdempotencyStore, PaymentService, FakeProcessor, RetryPolicy,
transition, is_retryable, FingerprintMismatch, InProgress and IllegalTransition as used below.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("IDEMPOTENCY_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("idem_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
PAY = {"amount": 1999, "currency": "BRL", "customer": "cus_1"}


def service(script=None, **policy):
    proc = m.FakeProcessor(script)
    svc = m.PaymentService(m.IdempotencyStore(), proc, m.RetryPolicy(**policy) if policy else m.RetryPolicy())
    return svc, proc


def test_same_key_twice_charges_once_and_replays_the_response():
    svc, proc = service()
    first = svc.charge("t1", "k1", PAY)
    second = svc.charge("t1", "k1", PAY)
    assert first == second
    assert first["status"] == "succeeded"
    assert proc.calls == 1 and len(proc.charges) == 1


def test_same_key_different_payload_is_refused():
    svc, proc = service()
    svc.charge("t1", "k1", PAY)
    with pytest.raises(m.FingerprintMismatch):
        svc.charge("t1", "k1", {**PAY, "amount": 2999})
    assert proc.calls == 1


def test_keys_are_scoped_by_tenant_and_operation():
    store = m.IdempotencyStore()
    assert store.begin("t1", "charge", "k", PAY)[0] == "new"
    assert store.begin("t2", "charge", "k", PAY)[0] == "new"
    assert store.begin("t1", "refund", "k", PAY)[0] == "new"
    assert len(store) == 3


def test_concurrent_duplicate_sees_in_progress_then_replays():
    store = m.IdempotencyStore()
    assert store.begin("t1", "charge", "k", PAY) == ("new", None)
    with pytest.raises(m.InProgress):
        store.begin("t1", "charge", "k", PAY)
    store.complete("t1", "charge", "k", {"status": "succeeded"})
    assert store.begin("t1", "charge", "k", PAY) == ("replay", {"status": "succeeded"})


def test_stored_response_is_a_copy():
    store = m.IdempotencyStore()
    store.begin("t1", "charge", "k", PAY)
    resp = {"status": "succeeded", "ref": "ch_1"}
    store.complete("t1", "charge", "k", resp)
    resp["ref"] = "mutated"
    assert store.begin("t1", "charge", "k", PAY)[1]["ref"] == "ch_1"


def test_timeout_is_unknown_outcome_and_retry_with_same_key_charges_once():
    svc, proc = service(["timeout", "ok"])
    first = svc.charge("t1", "k1", PAY)
    assert first["status"] == "pending"
    assert len(proc.charges) == 1  # the processor did charge
    second = svc.charge("t1", "k1", PAY)
    assert second["status"] == "succeeded"
    assert len(proc.charges) == 1
    assert svc.intents[m.PaymentService.operation_id("t1", "k1")]["status"] == "succeeded"


def test_persist_before_call_and_reconciler_resolves_from_processor():
    svc, proc = service(["timeout"])
    svc.charge("t1", "k1", PAY)  # times out after the processor charged
    report = svc.reconcile_pending()
    assert report == {"resolved": 1, "pending": 0}
    assert len(proc.charges) == 1
    assert svc.charge("t1", "k1", PAY)["status"] == "succeeded"
    assert proc.calls == 1


def test_crash_between_persist_and_call_leaves_a_pending_intent():
    svc, proc = service()
    svc.store.begin("t1", "k9", "charge", PAY) if False else None
    svc.persist_intent("t1", "k9", PAY)  # the process died before calling the processor
    report = svc.reconcile_pending()
    assert report == {"resolved": 0, "pending": 1}
    assert proc.calls == 0


def test_validation_error_is_final_and_not_retried():
    svc, proc = service(["400"])
    first = svc.charge("t1", "k1", PAY)
    assert first["status"] == "failed" and first["error"] == 400
    assert proc.calls == 1
    assert svc.charge("t1", "k1", PAY) == first  # the failure replays too


def test_server_error_retries_with_backoff_and_same_key():
    delays = []
    svc, proc = service(["500", "503", "ok"], max_attempts=3)
    svc.sleeper = delays.append
    result = svc.charge("t1", "k1", PAY)
    assert result["status"] == "succeeded"
    assert proc.calls == 3 and len(proc.charges) == 1
    assert delays == [0.2, 0.4]


def test_retries_are_bounded():
    svc, proc = service(["500", "500", "500", "ok"], max_attempts=3)
    svc.sleeper = lambda s: None
    result = svc.charge("t1", "k1", PAY)
    assert result["status"] == "pending"
    assert proc.calls == 3


@pytest.mark.parametrize("status,retryable", [(None, True), (429, True), (500, True), (503, True), (400, False), (402, False), (404, False), (422, False), (200, False)])
def test_is_retryable(status, retryable):
    assert m.is_retryable(status) is retryable


def test_state_machine_happy_path_and_guards():
    s = "created"
    for event in ("authorize", "capture", "settle"):
        s = m.transition(s, event)
    assert s == "settled"
    assert m.transition("settled", "partial_refund") == "partially_refunded"
    assert m.transition("partially_refunded", "refund") == "refunded"
    with pytest.raises(m.IllegalTransition):
        m.transition("captured", "capture")
    with pytest.raises(m.IllegalTransition):
        m.transition("refunded", "refund")
    with pytest.raises(m.IllegalTransition):
        m.transition("created", "capture")
