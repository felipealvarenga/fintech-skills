"""Unrun tests (no shell/deps verified). Needs pytest and flask."""
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from unittest import mock

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

SECRET = "whsec_test"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_DB", str(tmp_path / "w.db"))
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRETS", SECRET)
    monkeypatch.setenv("STRIPE_LIVEMODE", "false")
    import importlib
    import stripe_webhook as m
    importlib.reload(m)
    m.mark_paid = mock.Mock()
    app = Flask(__name__)
    app.add_url_rule("/wh", view_func=m.stripe_webhook, methods=["POST"])
    return m, app.test_client()


def _event(eid="evt_1", livemode=False):
    # Deliberately non-canonical JSON (spaces) to prove we verify raw bytes.
    return json.dumps({"id": eid, "type": "payment_intent.succeeded", "livemode": livemode,
                       "data": {"object": {"id": "pi_1", "metadata": {"order_id": "o1"}}}},
                      indent=2).encode()


def _sign(body, ts=None, secret=SECRET):
    ts = int(ts or time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _post(c, body, header):
    return c.post("/wh", data=body, headers={"Stripe-Signature": header})


def _pi(status):
    return {"status": status, "metadata": {"order_id": "o1"}}


def _count(m):
    return m._db().execute("SELECT COUNT(*) FROM webhook_events").fetchone()[0]


def test_invalid_signature(env):
    m, c = env
    assert _post(c, _event(), _sign(_event(), secret="wrong")).status_code == 400
    assert _count(m) == 0
    m.mark_paid.assert_not_called()


def test_stale_timestamp(env):
    m, c = env
    body = _event()
    assert _post(c, body, _sign(body, ts=time.time() - 3600)).status_code == 400
    assert _count(m) == 0


def test_valid_event_stored_and_processed_once(env):
    m, c = env
    body = _event()
    assert _post(c, body, _sign(body)).status_code == 200
    with mock.patch("stripe.PaymentIntent.retrieve", return_value=_pi("succeeded")):
        m.process_pending()
        m.process_pending()
    m.mark_paid.assert_called_once_with("o1")


def test_duplicate_event_id(env):
    m, c = env
    body = _event()
    assert _post(c, body, _sign(body)).status_code == 200
    assert _post(c, body, _sign(body)).status_code == 200
    assert _count(m) == 1
    with mock.patch("stripe.PaymentIntent.retrieve", return_value=_pi("succeeded")):
        m.process_pending()
    m.mark_paid.assert_called_once()


def test_payload_paid_but_api_pending(env):
    m, c = env
    body = _event()
    _post(c, body, _sign(body))
    with mock.patch("stripe.PaymentIntent.retrieve", return_value=_pi("processing")):
        m.process_pending()
    m.mark_paid.assert_not_called()


def test_failure_marked_failed_then_replay(env):
    m, c = env
    body = _event()
    assert _post(c, body, _sign(body)).status_code == 200
    m.mark_paid.side_effect = RuntimeError("db down")
    with mock.patch("stripe.PaymentIntent.retrieve", return_value=_pi("succeeded")):
        m.process_event("evt_1")
        status = m._db().execute("SELECT status FROM webhook_events").fetchone()[0]
        assert status == "failed"
        m.mark_paid.side_effect = None
        m.process_event("evt_1")
    assert m._db().execute("SELECT status FROM webhook_events").fetchone()[0] == "processed"


def test_livemode_event_refused_on_test_endpoint(env):
    m, c = env
    body = _event(livemode=True)
    assert _post(c, body, _sign(body)).status_code == 400
    assert _count(m) == 0


def test_secret_rotation(env, monkeypatch):
    m, c = env
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRETS", f"whsec_new,{SECRET}")
    body = _event()
    assert _post(c, body, _sign(body)).status_code == 200
