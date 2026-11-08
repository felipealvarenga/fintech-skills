"""Non-happy-path idempotency tests for PaymentService.charge.

ASSUMPTIONS (payments.py is interface-only, so these are not verifiable yet):
  * FakeProcessor(script=[...]) consumes one entry per processor call; an entry
    that is an Exception instance is raised, anything else is returned.
  * FakeProcessor exposes `.calls`, a list with one item per processor call.
  * Reusing a key with a different payload raises an exception.
  * A processor exception is not cached, so retrying the same key reaches the
    processor again.
Adjust these helpers/assertions to match the real implementation.
"""
import threading

import pytest

from payments import PaymentService, FakeProcessor, IdempotencyStore


def make(script=None):
    proc = FakeProcessor(script)
    return PaymentService(IdempotencyStore(), proc), proc


def test_replay_returns_same_result_without_recharging():
    svc, proc = make()
    first = svc.charge("t1", "k1", {"amount": 1000})
    second = svc.charge("t1", "k1", {"amount": 1000})
    assert second == first
    assert len(proc.calls) == 1


def test_many_replays_charge_once():
    svc, proc = make()
    results = [svc.charge("t1", "k1", {"amount": 1000}) for _ in range(5)]
    assert all(r == results[0] for r in results)
    assert len(proc.calls) == 1


def test_same_key_different_payload_is_rejected():
    svc, proc = make()
    svc.charge("t1", "k1", {"amount": 1000})
    with pytest.raises(Exception):
        svc.charge("t1", "k1", {"amount": 2000})
    assert len(proc.calls) == 1


def test_different_keys_are_independent_charges():
    svc, proc = make()
    svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t1", "k2", {"amount": 1000})
    assert len(proc.calls) == 2


def test_same_key_different_tenants_do_not_collide():
    svc, proc = make()
    svc.charge("t1", "k1", {"amount": 1000})
    r2 = svc.charge("t2", "k1", {"amount": 5000})  # must not raise a payload conflict
    assert r2["status"] == "succeeded"
    assert len(proc.calls) == 2


def test_tenant_cannot_see_another_tenants_cached_result():
    svc, proc = make()
    r1 = svc.charge("t1", "k1", {"amount": 1000})
    r2 = svc.charge("t2", "k1", {"amount": 1000})
    assert r2 is not r1
    assert len(proc.calls) == 2


def test_processor_error_is_not_cached_and_retry_succeeds():
    svc, proc = make([RuntimeError("timeout"), {"status": "succeeded"}])
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", {"amount": 1000})
    result = svc.charge("t1", "k1", {"amount": 1000})
    assert result["status"] == "succeeded"
    assert len(proc.calls) == 2


def test_success_after_retry_is_then_cached():
    svc, proc = make([RuntimeError("timeout"), {"status": "succeeded"}])
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", {"amount": 1000})
    first = svc.charge("t1", "k1", {"amount": 1000})
    again = svc.charge("t1", "k1", {"amount": 1000})
    assert again == first
    assert len(proc.calls) == 2


def test_failed_attempt_does_not_block_payload_change():
    # A key whose only attempt errored never completed, so it shouldn't be locked
    # to the first payload.
    svc, proc = make([RuntimeError("boom"), {"status": "succeeded"}])
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", {"amount": 1000})
    assert svc.charge("t1", "k1", {"amount": 2000})["status"] == "succeeded"


def test_concurrent_same_key_charges_once():
    svc, proc = make()
    results, errors = [], []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            results.append(svc.charge("t1", "k1", {"amount": 1000}))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(proc.calls) == 1
    assert not errors
    assert all(r == results[0] for r in results)


@pytest.mark.parametrize("key", ["", None])
def test_invalid_key_is_rejected(key):
    svc, proc = make()
    with pytest.raises(Exception):
        svc.charge("t1", key, {"amount": 1000})
    assert len(proc.calls) == 0
