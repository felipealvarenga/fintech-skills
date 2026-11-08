import json
import time
from unittest import mock

import pytest
import stripe
from flask import Flask

from src import stripe_webhook as wh

SECRET = "whsec_test"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRETS", SECRET)
    monkeypatch.setattr(wh, "DB_PATH", str(tmp_path / "w.db"))
    wh.mark_paid = mock.Mock()
    app = Flask(__name__)
    app.add_url_rule("/hook", view_func=wh.stripe_webhook, methods=["POST"])
    return app.test_client()


def signed(payload, ts=None, secret=SECRET):
    body = json.dumps(payload)
    ts = ts or int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{body}", secret)
    return body, {"Stripe-Signature": f"t={ts},v1={sig}"}


def event(eid="evt_1"):
    return {"id": eid, "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_1"}}}


def intent(status="succeeded"):
    return {"status": status, "metadata": {"order_id": "o1"}}


def test_invalid_signature_rejected(client):
    body, _ = signed(event())
    r = client.post("/hook", data=body, headers={"Stripe-Signature": "t=1,v1=bad"})
    assert r.status_code == 400
    wh.mark_paid.assert_not_called()


def test_stale_timestamp_rejected(client):
    body, h = signed(event(), ts=int(time.time()) - 3600)
    assert client.post("/hook", data=body, headers=h).status_code == 400
    wh.mark_paid.assert_not_called()


def test_valid_event_processed_once_and_duplicate_acked(client):
    body, h = signed(event())
    with mock.patch.object(stripe.PaymentIntent, "retrieve", return_value=intent()):
        assert client.post("/hook", data=body, headers=h).status_code == 200
        assert client.post("/hook", data=body, headers=h).status_code == 200
    wh.mark_paid.assert_called_once_with("o1")


def test_payload_says_paid_api_says_pending(client):
    body, h = signed(event())
    with mock.patch.object(stripe.PaymentIntent, "retrieve", return_value=intent("processing")):
        assert client.post("/hook", data=body, headers=h).status_code == 200
    wh.mark_paid.assert_not_called()


def test_rotation_accepts_old_secret(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRETS", f"whsec_new,{SECRET}")
    body, h = signed(event("evt_2"))
    with mock.patch.object(stripe.PaymentIntent, "retrieve", return_value=intent()):
        assert client.post("/hook", data=body, headers=h).status_code == 200
