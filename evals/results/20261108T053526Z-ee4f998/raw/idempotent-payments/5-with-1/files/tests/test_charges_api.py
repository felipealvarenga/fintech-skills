import os
import sys
import threading
from types import SimpleNamespace

import pytest
import stripe

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import charges_api as api  # noqa: E402


class FakeProcessor(api.Processor):
    """Dedupes by idempotency key like Stripe. `script` is a list of per-call behaviours:
    'ok', 'timeout' (charge is created, then connection error), 'timeout_nocreate',
    'declined', 'bad_request', 'unavailable'."""

    def __init__(self, script=(), policy=None):
        super().__init__(policy or api.RetryPolicy(max_attempts=1), lambda s: None)
        self.script, self.by_key, self.calls, self.keys = list(script), {}, 0, []
        self.lock = threading.Lock()

    def create(self, charge_id, amount, currency):
        key = f"charge:{charge_id}"
        with self.lock:
            self.calls += 1
            self.keys.append(key)
            step = self.script.pop(0) if self.script else "ok"
            if step == "declined":
                raise stripe.error.CardError("declined", "p", "card_declined")
            if step == "bad_request":
                raise stripe.error.InvalidRequestError("bad", "amount")
            if step == "unavailable":
                raise stripe.error.APIError("503")
            if step == "timeout_nocreate":
                raise stripe.error.APIConnectionError("timeout")
            if key not in self.by_key:
                self.by_key[key] = SimpleNamespace(
                    id=f"pi_{len(self.by_key)}", status="succeeded", charge_id=charge_id)
            if step == "timeout":
                raise stripe.error.APIConnectionError("timeout")
            return self.by_key[key]

    def find(self, charge_id):
        return self.by_key.get(f"charge:{charge_id}")

    @property
    def charges(self):
        return len(self.by_key)


def req(key="k1", amount=1000, currency="usd"):
    return SimpleNamespace(json={"amount": amount, "currency": currency},
                           headers={"Idempotency-Key": key})


@pytest.fixture
def store():
    return api.Store()


def test_same_key_same_payload_one_charge(store):
    p = FakeProcessor()
    a = api.create_charge(req(), store, p)
    b = api.create_charge(req(), store, p)
    assert a == b and p.charges == 1 and p.calls == 1


def test_same_key_different_amount_errors(store):
    p = FakeProcessor()
    api.create_charge(req(amount=1000), store, p)
    body, status = api.create_charge(req(amount=2000), store, p)
    assert status == 422 and p.charges == 1


def test_concurrent_same_key_one_charge(store):
    p = FakeProcessor()
    out = []
    ts = [threading.Thread(target=lambda: out.append(api.create_charge(req(), store, p)))
          for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert p.charges == 1 and out[0] == out[1]


def test_timeout_leaves_pending_then_retry_same_key_one_charge(store):
    p = FakeProcessor(["timeout"])
    body, status = api.create_charge(req(), store, p)
    assert status == 202 and body["status"] == "pending"
    assert store.get(body["id"])["status"] == "pending"  # never failed on timeout
    body2, status2 = api.create_charge(req(), store, p)
    assert status2 == 200 and body2["status"] == "captured"
    assert p.charges == 1 and len(set(p.keys)) == 1  # same outbound key both times


def test_timeout_client_disappears_reconciler_resolves(store):
    p = FakeProcessor(["timeout"])
    body, _ = api.create_charge(req(), store, p)
    assert api.reconcile_pending(store, p, older_than_seconds=-1) == []
    assert store.get(body["id"])["status"] == "captured"


def test_reconciler_keeps_unfound_pending(store):
    p = FakeProcessor(["timeout_nocreate"])
    body, _ = api.create_charge(req(), store, p)
    assert api.reconcile_pending(store, p, older_than_seconds=-1) == [body["id"]]
    assert store.get(body["id"])["status"] == "pending"


def test_confirmed_decline_marks_failed(store):
    p = FakeProcessor(["declined"])
    body, _ = api.create_charge(req(), store, p)
    assert body["status"] == "failed"


def test_capture_on_captured_rejected_with_state(store):
    p = FakeProcessor()
    body, _ = api.create_charge(req(), store, p)  # captured
    err, status = api.capture_charge(store, p, body["id"])
    assert status == 409 and err["status"] == "captured"


def test_400_not_retried_503_retried_to_limit():
    sleeps = []
    policy = api.RetryPolicy(max_attempts=3)
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise stripe.error.InvalidRequestError("bad", "x")

    with pytest.raises(stripe.error.InvalidRequestError):
        api.call_with_retry(bad, policy, sleeps.append)
    assert calls["n"] == 1 and sleeps == []

    calls["n"] = 0

    def unavailable():
        calls["n"] += 1
        raise stripe.error.APIError("503")

    with pytest.raises(stripe.error.APIError):
        api.call_with_retry(unavailable, policy, sleeps.append)
    assert calls["n"] == 3 and len(sleeps) == 2


def test_outbox_one_event_per_transition(store):
    p = FakeProcessor()
    api.create_charge(req(), store, p)
    api.create_charge(req(), store, p)  # replay: no new event
    rows = store.db.execute("SELECT type FROM outbox").fetchall()
    assert [r["type"] for r in rows] == ["charge.captured"]
