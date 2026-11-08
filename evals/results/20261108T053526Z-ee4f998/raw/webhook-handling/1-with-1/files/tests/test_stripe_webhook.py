import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import stripe_webhook as sw  # noqa: E402

SECRET = "whsec_test"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sw, "DB_PATH", str(tmp_path / "w.db"))
    monkeypatch.setattr(sw, "EXPECT_LIVEMODE", False)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRETS", SECRET)
    paid, queue = [], []
    monkeypatch.setattr(sw, "mark_paid", lambda oid, **kw: paid.append(oid))
    monkeypatch.setattr(sw, "enqueue", lambda eid: queue.append(eid))
    state = {"status": "succeeded"}
    monkeypatch.setattr(
        sw.stripe.PaymentIntent, "retrieve",
        lambda pid: {"id": pid, "status": state["status"], "amount_received": 100,
                     "currency": "usd", "metadata": {"order_id": "o1"}},
    )
    app = Flask(__name__)
    app.add_url_rule("/wh", view_func=sw.stripe_webhook, methods=["POST"])
    return app.test_client(), paid, queue, state


def signed(body: dict, ts=None, secret=SECRET):
    raw = json.dumps(body).encode()
    ts = int(ts or time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {"Stripe-Signature": f"t={ts},v1={sig}"}


def evt(eid="evt_1", livemode=False):
    return {"id": eid, "object": "event", "type": "payment_intent.succeeded",
            "livemode": livemode, "data": {"object": {"id": "pi_1", "object": "payment_intent"}}}


def drain(queue):
    for eid in list(queue):
        sw.process_event(eid)


def test_invalid_signature(env):
    c, paid, q, _ = env
    raw, h = signed(evt(), secret="wrong")
    assert c.post("/wh", data=raw, headers=h).status_code == 400
    assert q == [] and paid == []


def test_stale_timestamp(env):
    c, paid, q, _ = env
    raw, h = signed(evt(), ts=time.time() - 3600)
    assert c.post("/wh", data=raw, headers=h).status_code == 400
    assert q == []


def test_valid_event_processed_once(env):
    c, paid, q, _ = env
    raw, h = signed(evt())
    assert c.post("/wh", data=raw, headers=h).status_code == 200
    drain(q)
    assert paid == ["o1"]


def test_duplicate_event(env):
    c, paid, q, _ = env
    raw, h = signed(evt())
    assert c.post("/wh", data=raw, headers=h).status_code == 200
    assert c.post("/wh", data=raw, headers=h).status_code == 200
    drain(q)
    drain(q)
    assert paid == ["o1"] and len(q) == 1


def test_payload_paid_but_api_pending(env):
    c, paid, q, state = env
    state["status"] = "processing"
    raw, h = signed(evt())
    c.post("/wh", data=raw, headers=h)
    drain(q)
    assert paid == []


def test_handler_failure_then_replay(env, monkeypatch):
    c, paid, q, _ = env
    def boom(oid, **kw):
        raise RuntimeError("db down")
    monkeypatch.setattr(sw, "mark_paid", boom)
    raw, h = signed(evt())
    assert c.post("/wh", data=raw, headers=h).status_code == 200
    drain(q)
    assert paid == []
    monkeypatch.setattr(sw, "mark_paid", lambda oid, **kw: paid.append(oid))
    sw.replay("evt_1")
    assert paid == ["o1"]


def test_live_event_on_test_endpoint(env):
    c, paid, q, _ = env
    raw, h = signed(evt(livemode=True))
    assert c.post("/wh", data=raw, headers=h).status_code == 400
    assert q == []


def test_secret_rotation(env, monkeypatch):
    c, paid, q, _ = env
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRETS", "whsec_new," + SECRET)
    raw, h = signed(evt())
    assert c.post("/wh", data=raw, headers=h).status_code == 200
