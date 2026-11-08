import sys
import threading
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import charges_api as api  # noqa: E402


class Req:
    def __init__(self, amount=1000, currency="usd", key="k1", tenant="t1"):
        self.json = {"amount": amount, "currency": currency}
        self.headers = {"Idempotency-Key": key, "X-Tenant-Id": tenant} if key else {}


class FakeProcessor:
    """Behaves like Stripe: same key -> same charge. Can time out *after* creating."""

    def __init__(self):
        self.by_key, self.creations, self.timeouts = {}, 0, 0
        self.gate = None

    def create_charge(self, op_id, amount, currency):
        if self.gate:
            self.gate.wait(2)
        key = f"charge:{op_id}"
        if key not in self.by_key:
            self.creations += 1
            self.by_key[key] = {"id": f"pi_{self.creations}", "status": "succeeded"}
        if self.timeouts:
            self.timeouts -= 1
            raise api.OutcomeUnknown("timeout")
        return self.by_key[key]


@pytest.fixture
def store():
    return api.IdempotencyStore()


def test_same_key_same_payload_one_charge(store):
    p = FakeProcessor()
    a = api.create_charge(Req(), store, p)
    b = api.create_charge(Req(), store, p)
    assert a == b and a[1] == 200 and p.creations == 1


def test_same_key_different_amount_rejected(store):
    p = FakeProcessor()
    api.create_charge(Req(amount=1000), store, p)
    body, status = api.create_charge(Req(amount=2000), store, p)
    assert status == 422 and p.creations == 1


def test_missing_key_rejected(store):
    assert api.create_charge(Req(key=None), store, FakeProcessor())[1] == 400


def test_keys_scoped_per_tenant(store):
    p = FakeProcessor()
    api.create_charge(Req(tenant="a"), store, p)
    api.create_charge(Req(tenant="b"), store, p)
    assert p.creations == 2


def test_concurrent_same_key_one_charge(store):
    p = FakeProcessor()
    p.gate = threading.Event()
    results = []
    ts = [threading.Thread(target=lambda: results.append(api.create_charge(Req(), store, p)))
          for _ in range(2)]
    for t in ts:
        t.start()
    p.gate.set()
    for t in ts:
        t.join()
    assert p.creations == 1
    assert sorted(s for _, s in results) in ([200, 200], [200, 409])
    assert api.create_charge(Req(), store, p)[1] == 200   # replay returns the winner's response


def test_timeout_then_retry_same_key_one_charge(store):
    p = FakeProcessor()
    p.timeouts = 1
    _, status = api.create_charge(Req(), store, p)
    assert status == 504
    body, status = api.create_charge(Req(), store, p)
    assert status == 200 and p.creations == 1 and body["id"] == "pi_1"


def test_timeout_client_gone_reconciler_resolves(store):
    p = FakeProcessor()
    p.timeouts = 1
    api.create_charge(Req(), store, p)
    assert store.get("t1", "k1")["state"] == "unknown"
    assert api.reconcile(store, p, older_than_s=-1) == 1
    row = store.get("t1", "k1")
    assert row["state"] == "succeeded" and p.creations == 1


# ---- StripeProcessor: outbound key + retry policy
class HttpErr(Exception):
    def __init__(self, status):
        super().__init__(str(status))
        self.http_status = status


def _patch_stripe(monkeypatch, outcomes, calls):
    def create(**kw):
        calls.append(kw)
        o = outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return types.SimpleNamespace(id="pi_x", status="succeeded")
    monkeypatch.setattr(api.stripe, "PaymentIntent", types.SimpleNamespace(create=create))


def test_400_not_retried(monkeypatch):
    calls = []
    _patch_stripe(monkeypatch, [HttpErr(400)], calls)
    proc = api.StripeProcessor(api.RetryPolicy(sleep=lambda s: None))
    with pytest.raises(api.ProcessorRejected):
        proc.create_charge("op1", 100, "usd")
    assert len(calls) == 1


def test_503_retried_with_same_key_up_to_limit(monkeypatch):
    calls, sleeps = [], []
    _patch_stripe(monkeypatch, [HttpErr(503)] * 3, calls)
    proc = api.StripeProcessor(api.RetryPolicy(max_attempts=3, sleep=sleeps.append))
    with pytest.raises(api.OutcomeUnknown):
        proc.create_charge("op1", 100, "usd")
    assert len(calls) == 3 and len(sleeps) == 2
    assert {c["idempotency_key"] for c in calls} == {"charge:op1"}


def test_503_then_success(monkeypatch):
    calls = []
    _patch_stripe(monkeypatch, [HttpErr(503), None], calls)
    proc = api.StripeProcessor(api.RetryPolicy(sleep=lambda s: None))
    assert proc.create_charge("op1", 100, "usd")["id"] == "pi_x"
    assert len(calls) == 2
