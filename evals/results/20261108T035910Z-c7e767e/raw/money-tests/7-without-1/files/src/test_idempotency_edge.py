"""Idempotency tests beyond the happy path.

ASSUMPTIONS (payments.py is interface-only, so these are unverified; adjust to the real implementation):
  * FakeProcessor(script) takes a list of outcomes consumed one per processor call;
    an Exception instance in the list is raised, anything else is returned.
  * FakeProcessor exposes `.calls`, the number of times it was invoked.
  * Reusing a key with a different payload raises ValueError.
  * A failed charge is not cached, so retrying the same key re-attempts it.
"""
import threading

import pytest

from payments import PaymentService, FakeProcessor, IdempotencyStore

OK = {"status": "succeeded"}


def make(script=None):
    proc = FakeProcessor(script)
    return PaymentService(IdempotencyStore(), proc), proc


def test_replay_returns_same_result_without_recharging():
    svc, proc = make([OK, OK])
    first = svc.charge("t1", "k1", {"amount": 1000})
    second = svc.charge("t1", "k1", {"amount": 1000})
    assert second == first
    assert proc.calls == 1


def test_many_replays_charge_once():
    svc, proc = make([OK] * 10)
    results = [svc.charge("t1", "k1", {"amount": 1000}) for _ in range(10)]
    assert all(r == results[0] for r in results)
    assert proc.calls == 1


def test_different_keys_are_independent_charges():
    svc, proc = make([OK, OK])
    svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t1", "k2", {"amount": 1000})
    assert proc.calls == 2


def test_same_key_different_payload_is_rejected():
    svc, proc = make([OK, OK])
    svc.charge("t1", "k1", {"amount": 1000})
    with pytest.raises(ValueError):
        svc.charge("t1", "k1", {"amount": 2000})
    assert proc.calls == 1


def test_payload_key_order_does_not_matter():
    svc, proc = make([OK, OK])
    a = svc.charge("t1", "k1", {"amount": 1000, "currency": "USD"})
    b = svc.charge("t1", "k1", {"currency": "USD", "amount": 1000})
    assert a == b
    assert proc.calls == 1


def test_same_key_different_tenants_are_isolated():
    svc, proc = make([OK, OK])
    svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t2", "k1", {"amount": 1000})
    assert proc.calls == 2


def test_tenant_cannot_read_other_tenants_cached_result():
    svc, _ = make([{"status": "succeeded", "id": "a"}, {"status": "succeeded", "id": "b"}])
    r1 = svc.charge("t1", "k1", {"amount": 1000})
    r2 = svc.charge("t2", "k1", {"amount": 1000})
    assert r1 != r2


def test_processor_error_propagates():
    svc, _ = make([RuntimeError("boom")])
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", {"amount": 1000})


def test_failed_charge_is_not_cached_and_can_be_retried():
    svc, proc = make([RuntimeError("boom"), OK])
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", {"amount": 1000})
    assert svc.charge("t1", "k1", {"amount": 1000})["status"] == "succeeded"
    assert proc.calls == 2


def test_success_after_retry_is_then_replayed():
    svc, proc = make([RuntimeError("boom"), OK, OK])
    with pytest.raises(RuntimeError):
        svc.charge("t1", "k1", {"amount": 1000})
    first = svc.charge("t1", "k1", {"amount": 1000})
    assert svc.charge("t1", "k1", {"amount": 1000}) == first
    assert proc.calls == 2


def test_concurrent_same_key_charges_once():
    svc, proc = make([OK] * 8)
    results, errors = [], []

    def run():
        try:
            results.append(svc.charge("t1", "k1", {"amount": 1000}))
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert proc.calls == 1
    assert all(r == results[0] for r in results)


@pytest.mark.parametrize("key", ["", None])
def test_invalid_key_is_rejected(key):
    svc, proc = make([OK])
    with pytest.raises((ValueError, TypeError)):
        svc.charge("t1", key, {"amount": 1000})
    assert proc.calls == 0
