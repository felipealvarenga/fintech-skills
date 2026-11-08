"""Unrun: no shell/dependencies were available when written. Needs pytest, flask, stripe."""
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
    monkeypatch.setattr(sw, "EXPECT_LIVE", False)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    calls = {"paid": [], "refunded": [], "disputed": [], "queued": []}
    sw.mark_paid = lambda o: calls["paid"].append(o)
    sw.mark_refunded = lambda o, amt, full: calls["refunded"].append((o, amt, full))
    sw.mark_disputed = lambda o, d, s, a: calls["disputed"].append((o, d, s))
    monkeypatch.setattr(sw, "enqueue", lambda eid: calls["queued"].append(eid))
    app = Flask(__name__)
    app.add_url_rule("/w", view_func=sw.stripe_webhook, methods=["POST"])
    return app.test_client(), calls, monkeypatch


def signed(event, ts=None, secret=SECRET):
    body = json.dumps(event).encode()
    ts = int(ts or time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}"}


def ev(eid, etype, obj, live=False):
    return {"id": eid, "type": etype, "livemode": live, "data": {"object": obj}}


def count(n=None):
    with sw._db() as db:
        return db.execute("SELECT COUNT(*) FROM webhook_events").fetchone()[0]


def test_invalid_signature(env):
    c, calls, _ = env
    body, h = signed(ev("evt_1", "charge.refunded", {"id": "ch_1"}), secret="wrong")
    assert c.post("/w", data=body, headers=h).status_code == 400
    assert count() == 0 and not calls["queued"]


def test_stale_timestamp(env):
    c, calls, _ = env
    body, h = signed(ev("evt_1", "charge.refunded", {"id": "ch_1"}), ts=time.time() - 3600)
    assert c.post("/w", data=body, headers=h).status_code == 400
    assert count() == 0


def test_live_event_on_test_endpoint(env):
    c, _, _ = env
    body, h = signed(ev("evt_1", "charge.refunded", {"id": "ch_1"}, live=True))
    assert c.post("/w", data=body, headers=h).status_code == 400
    assert count() == 0


def test_rotation_previous_secret(env):
    c, _, mp = env
    mp.setenv("STRIPE_WEBHOOK_SECRET", "whsec_new")
    mp.setenv("STRIPE_WEBHOOK_SECRET_PREVIOUS", SECRET)
    body, h = signed(ev("evt_1", "charge.refunded", {"id": "ch_1"}))
    assert c.post("/w", data=body, headers=h).status_code == 200


def test_refund_stored_acked_processed_once_and_duplicate(env):
    c, calls, mp = env
    mp.setattr(sw.stripe.Charge, "retrieve", lambda i: {
        "id": i, "metadata": {"order_id": "o1"}, "amount_refunded": 500, "refunded": False}, raising=False)
    body, h = signed(ev("evt_r", "charge.refunded", {"id": "ch_1"}))
    assert c.post("/w", data=body, headers=h).status_code == 200
    assert c.post("/w", data=body, headers=h).status_code == 200
    assert count() == 1 and calls["queued"] == ["evt_r"]
    sw.process_event("evt_r")
    sw.process_event("evt_r")
    assert calls["refunded"] == [("o1", 500, False)]


def test_dispute_uses_api_state(env):
    c, calls, mp = env
    mp.setattr(sw.stripe.Dispute, "retrieve", lambda i: {
        "id": i, "charge": "ch_1", "status": "needs_response", "amount": 900}, raising=False)
    mp.setattr(sw.stripe.Charge, "retrieve", lambda i: {
        "id": i, "metadata": {"order_id": "o2"}}, raising=False)
    body, h = signed(ev("evt_d", "charge.dispute.created", {"id": "dp_1"}))
    assert c.post("/w", data=body, headers=h).status_code == 200
    sw.process_event("evt_d")
    assert calls["disputed"] == [("o2", "dp_1", "needs_response")]


def test_payload_says_refunded_api_says_not(env):
    c, calls, mp = env
    mp.setattr(sw.stripe.Charge, "retrieve", lambda i: {
        "id": i, "metadata": {"order_id": "o1"}, "amount_refunded": 0, "refunded": False}, raising=False)
    body, h = signed(ev("evt_x", "charge.refunded", {"id": "ch_1", "amount_refunded": 500, "refunded": True}))
    c.post("/w", data=body, headers=h)
    sw.process_event("evt_x")
    assert calls["refunded"] == []


def test_payment_intent_payload_pending_in_api(env):
    c, calls, mp = env
    mp.setattr(sw.stripe.PaymentIntent, "retrieve", lambda i: {
        "id": i, "status": "processing", "metadata": {"order_id": "o3"}}, raising=False)
    body, h = signed(ev("evt_p", "payment_intent.succeeded", {"id": "pi_1", "status": "succeeded"}))
    c.post("/w", data=body, headers=h)
    sw.process_event("evt_p")
    assert calls["paid"] == []


def test_handler_failure_then_replay(env):
    c, calls, mp = env
    def boom(i):
        raise RuntimeError("api down")
    mp.setattr(sw.stripe.Charge, "retrieve", boom, raising=False)
    body, h = signed(ev("evt_f", "charge.refunded", {"id": "ch_1"}))
    assert c.post("/w", data=body, headers=h).status_code == 200
    sw.process_event("evt_f")
    with sw._db() as db:
        assert db.execute("SELECT status FROM webhook_events").fetchone()[0] == "failed"
    mp.setattr(sw.stripe.Charge, "retrieve", lambda i: {
        "id": i, "metadata": {"order_id": "o1"}, "amount_refunded": 100, "refunded": True}, raising=False)
    sw.replay_event("evt_f", who="felipe", reason="fixed api outage")
    assert calls["refunded"] == [("o1", 100, True)]
