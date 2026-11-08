"""Idempotency tests beyond the happy path (money-tests rule 8).

payments.py is interface only, so these tests pin down ASSUMED behaviour.
Adjust the ASSUMPTIONS block once the real contract is settled:

  * FakeProcessor(script): list of outcomes consumed one per processor call.
    "ok" -> succeeds, "timeout" -> raises TimeoutError, "decline" -> declined.
    After the script is exhausted it behaves as "ok".
  * FakeProcessor.calls: list of payloads actually sent to the processor.
  * charge() returns a dict with "status" ("succeeded" / "declined").
  * Same (tenant, key) with a different payload raises ValueError.
  * A timeout propagates as TimeoutError and leaves the key retryable.
"""
import threading

import pytest

from payments import FakeProcessor, IdempotencyStore, PaymentService

# ---- ASSUMPTIONS -----------------------------------------------------------
CONFLICT_EXC = ValueError
TIMEOUT_EXC = TimeoutError
# ----------------------------------------------------------------------------

P = {"amount": 1000}


def make(script=None):
    proc = FakeProcessor(script)
    store = IdempotencyStore()
    return PaymentService(store, proc), proc, store


def test_duplicate_request_charges_once_and_returns_same_result():
    svc, proc, _ = make()
    first = svc.charge("t1", "k1", P)
    second = svc.charge("t1", "k1", P)
    assert second == first
    assert len(proc.calls) == 1


def test_many_replays_still_one_charge():
    svc, proc, _ = make()
    results = [svc.charge("t1", "k1", P) for _ in range(20)]
    assert all(r == results[0] for r in results)
    assert len(proc.calls) == 1


def test_same_key_different_payload_is_rejected_and_not_charged():
    svc, proc, _ = make()
    svc.charge("t1", "k1", P)
    with pytest.raises(CONFLICT_EXC):
        svc.charge("t1", "k1", {"amount": 2000})
    assert len(proc.calls) == 1
    assert proc.calls[0]["amount"] == 1000


def test_same_key_different_tenants_are_independent():
    svc, proc, _ = make()
    svc.charge("t1", "k1", P)
    svc.charge("t2", "k1", P)
    assert len(proc.calls) == 2


def test_different_keys_same_payload_charge_separately():
    svc, proc, _ = make()
    svc.charge("t1", "k1", P)
    svc.charge("t1", "k2", P)
    assert len(proc.calls) == 2


def test_timeout_then_retry_with_same_key_succeeds_once():
    svc, proc, _ = make(["timeout", "ok"])
    with pytest.raises(TIMEOUT_EXC):
        svc.charge("t1", "k1", P)
    result = svc.charge("t1", "k1", P)
    assert result["status"] == "succeeded"
    # A third call must replay, not hit the processor again.
    assert svc.charge("t1", "k1", P) == result
    assert len(proc.calls) == 2  # timed-out attempt + one successful attempt


def test_timeout_does_not_cache_a_failure():
    svc, proc, _ = make(["timeout"])
    with pytest.raises(TIMEOUT_EXC):
        svc.charge("t1", "k1", P)
    assert svc.charge("t1", "k1", P)["status"] == "succeeded"


def test_decline_is_replayed_not_retried():
    svc, proc, _ = make(["decline", "ok"])
    first = svc.charge("t1", "k1", P)
    assert first["status"] == "declined"
    assert svc.charge("t1", "k1", P) == first
    assert len(proc.calls) == 1


def test_concurrent_requests_behind_barrier_charge_once():
    svc, proc, _ = make()
    n = 8
    barrier = threading.Barrier(n)
    results, errors = [], []

    def worker():
        barrier.wait()
        try:
            results.append(svc.charge("t1", "k1", P))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not any(t.is_alive() for t in threads)
    assert len(proc.calls) == 1
    assert not errors
    assert len(results) == n
    assert all(r == results[0] for r in results)


def test_fault_after_intent_persisted_before_processor_call(monkeypatch):
    """Crash between persisting the intent and calling the processor:
    a retry must complete exactly one charge, not zero and not two."""
    svc, proc, _ = make()
    real_charge = proc.charge if hasattr(proc, "charge") else None
    assert real_charge is not None, "FakeProcessor needs a charge method to inject a fault"
    state = {"boom": True}

    def flaky(*a, **kw):
        if state["boom"]:
            state["boom"] = False
            raise RuntimeError("crash before processor call")
        return real_charge(*a, **kw)

    monkeypatch.setattr(proc, "charge", flaky)
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", P)
    assert len(proc.calls) == 0
    result = svc.charge("t1", "k1", P)
    assert result["status"] == "succeeded"
    assert len(proc.calls) == 1
    assert svc.charge("t1", "k1", P) == result
    assert len(proc.calls) == 1
