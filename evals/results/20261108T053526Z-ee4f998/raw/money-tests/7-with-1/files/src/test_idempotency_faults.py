"""Idempotency tests beyond the happy path (UNRUN: payments.py is an interface stub).

ASSUMED CONTRACT (payments.py does not define it; adjust here if the real one differs):
  - FakeProcessor(script): list consumed one entry per processor call. Entries:
      "ok"       -> call succeeds
      "timeout"  -> call raises TimeoutError (the money may or may not have moved)
      "decline"  -> call returns/raises a declined result
    After the script is exhausted, calls succeed.
  - FakeProcessor.calls: list of the payloads actually sent to the processor
    (one entry per real charge attempt).
  - charge() returns a dict with "status" ("succeeded" / "declined" / ...).
  - Same (tenant, key) with a different payload raises ValueError.
  - Keys are scoped per tenant.
  - A retry after a timeout must reuse the same key at the processor and
    must not result in a second charge.
"""
import threading

import pytest

from payments import FakeProcessor, IdempotencyStore, PaymentService


def make(script=None):
    proc = FakeProcessor(script)
    return PaymentService(IdempotencyStore(), proc), proc


def charges(proc):
    return len(proc.calls)


def test_duplicate_request_charges_once_and_returns_same_result():
    svc, proc = make()
    first = svc.charge("t1", "k1", {"amount": 1000})
    second = svc.charge("t1", "k1", {"amount": 1000})
    assert first["status"] == "succeeded"
    assert second == first
    assert charges(proc) == 1


def test_many_sequential_replays_charge_once():
    svc, proc = make()
    results = [svc.charge("t1", "k1", {"amount": 1000}) for _ in range(20)]
    assert all(r == results[0] for r in results)
    assert charges(proc) == 1


def test_same_key_different_payload_is_rejected_without_charging():
    svc, proc = make()
    svc.charge("t1", "k1", {"amount": 1000})
    with pytest.raises(ValueError):
        svc.charge("t1", "k1", {"amount": 2000})
    assert charges(proc) == 1


def test_different_keys_are_independent_charges():
    svc, proc = make()
    svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t1", "k2", {"amount": 1000})
    assert charges(proc) == 2


def test_same_key_different_tenants_do_not_collide():
    svc, proc = make()
    a = svc.charge("t1", "k1", {"amount": 1000})
    b = svc.charge("t2", "k1", {"amount": 1000})
    assert a["status"] == b["status"] == "succeeded"
    assert charges(proc) == 2


def test_tenant_cannot_read_another_tenants_cached_result():
    svc, proc = make()
    svc.charge("t1", "k1", {"amount": 1000})
    # t2 reusing the key with a different payload must be a fresh charge,
    # not a ValueError or t1's cached response.
    other = svc.charge("t2", "k1", {"amount": 555})
    assert other["status"] == "succeeded"
    assert proc.calls[-1]["amount"] == 555


def test_timeout_then_retry_with_same_key_ends_with_one_charge():
    svc, proc = make(["timeout", "ok"])
    with pytest.raises(TimeoutError):
        svc.charge("t1", "k1", {"amount": 1000})
    result = svc.charge("t1", "k1", {"amount": 1000})
    assert result["status"] == "succeeded"
    # Both attempts may reach the processor, but they must carry the same
    # idempotency key so the processor collapses them into one charge.
    assert len({c.get("idempotency_key") for c in proc.calls}) == 1


def test_success_result_is_cached_after_timeout_recovery():
    svc, proc = make(["timeout", "ok"])
    with pytest.raises(TimeoutError):
        svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t1", "k1", {"amount": 1000})
    n = charges(proc)
    svc.charge("t1", "k1", {"amount": 1000})
    assert charges(proc) == n


def test_declined_result_is_replayed_not_retried():
    svc, proc = make(["decline", "ok"])
    first = svc.charge("t1", "k1", {"amount": 1000})
    second = svc.charge("t1", "k1", {"amount": 1000})
    assert first["status"] == "declined"
    assert second == first
    assert charges(proc) == 1


def test_declined_then_new_key_can_succeed():
    svc, proc = make(["decline", "ok"])
    assert svc.charge("t1", "k1", {"amount": 1000})["status"] == "declined"
    assert svc.charge("t1", "k2", {"amount": 1000})["status"] == "succeeded"


def test_fault_between_intent_and_processor_call_does_not_double_charge():
    # Processor blows up on the first call (intent already persisted).
    svc, proc = make(["timeout", "ok", "ok"])
    with pytest.raises(TimeoutError):
        svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t1", "k1", {"amount": 1000})
    svc.charge("t1", "k1", {"amount": 1000})
    assert len({c.get("idempotency_key") for c in proc.calls}) == 1
    # After recovery, further replays never reach the processor again.
    assert charges(proc) == 2


def test_failed_attempt_does_not_poison_the_key():
    svc, _ = make(["timeout", "ok"])
    with pytest.raises(TimeoutError):
        svc.charge("t1", "k1", {"amount": 1000})
    assert svc.charge("t1", "k1", {"amount": 1000})["status"] == "succeeded"


def test_concurrent_identical_requests_charge_once():
    svc, proc = make()
    n = 16
    barrier = threading.Barrier(n)
    results, errors = [], []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        try:
            r = svc.charge("t1", "k1", {"amount": 1000})
            with lock:
                results.append(r)
        except Exception as e:  # noqa: BLE001
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not any(t.is_alive() for t in threads)
    assert charges(proc) == 1
    assert not errors
    assert len(results) == n
    assert all(r == results[0] for r in results)


def test_concurrent_requests_with_distinct_keys_all_charge():
    svc, proc = make()
    n = 8
    barrier = threading.Barrier(n)

    def worker(i):
        barrier.wait()
        svc.charge("t1", f"k{i}", {"amount": 100 + i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert charges(proc) == n
    assert sorted(c["amount"] for c in proc.calls) == [100 + i for i in range(n)]


def test_concurrent_same_key_with_first_call_timing_out_never_double_charges():
    svc, proc = make(["timeout"])
    n = 8
    barrier = threading.Barrier(n)

    def worker():
        barrier.wait()
        try:
            svc.charge("t1", "k1", {"amount": 1000})
        except TimeoutError:
            pass

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    svc.charge("t1", "k1", {"amount": 1000})
    assert len({c.get("idempotency_key") for c in proc.calls}) == 1
    assert svc.charge("t1", "k1", {"amount": 1000})["status"] == "succeeded"
    # Settled state: another replay adds no processor calls.
    before = charges(proc)
    svc.charge("t1", "k1", {"amount": 1000})
    assert charges(proc) == before


@pytest.mark.parametrize("amount", [0, 1, 999_999_999_999])
def test_replay_returns_exact_amount_for_edge_amounts(amount):
    svc, proc = make()
    first = svc.charge("t1", "k1", {"amount": amount})
    second = svc.charge("t1", "k1", {"amount": amount})
    assert second == first
    assert [c["amount"] for c in proc.calls] == [amount]
