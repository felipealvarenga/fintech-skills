"""Test vectors for webhook-handling.

Run against the reference: `pytest skills/webhook-handling`.
Run against your module:   `WEBHOOK_SOLUTION=/path/to/webhooks.py pytest skills/webhook-handling`.

The module under test must expose sign, verify, BadSignature, EventStore, apply_state,
response_status and receive as used below.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("WEBHOOK_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("webhook_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
SECRET = "whsec_test_1"
NOW = 1_800_000_000
BODY = b'{"id":"evt_1","type":"payment_intent.succeeded","data":{"object":{"id":"pi_1","status":"succeeded"}}}'


def test_valid_signature_passes():
    m.verify(m.sign(SECRET, BODY, NOW), BODY, [SECRET], NOW)


def test_wrong_secret_fails():
    with pytest.raises(m.BadSignature):
        m.verify(m.sign("whsec_other", BODY, NOW), BODY, [SECRET], NOW)


def test_tampered_body_fails():
    header = m.sign(SECRET, BODY, NOW)
    with pytest.raises(m.BadSignature):
        m.verify(header, BODY.replace(b"succeeded", b"failed"), [SECRET], NOW)


def test_parsed_then_reserialized_body_fails():
    # whitespace changes after a JSON round trip break the signature; verify the raw bytes
    header = m.sign(SECRET, BODY, NOW)
    pretty = json.dumps(json.loads(BODY), indent=2).encode()
    with pytest.raises(m.BadSignature):
        m.verify(header, pretty, [SECRET], NOW)


def test_non_bytes_body_is_refused():
    with pytest.raises(m.BadSignature):
        m.verify(m.sign(SECRET, BODY, NOW), BODY.decode(), [SECRET], NOW)  # type: ignore[arg-type]


@pytest.mark.parametrize("skew,ok", [(0, True), (299, True), (300, True), (301, False), (-301, False), (86400, False)])
def test_timestamp_tolerance(skew, ok):
    header = m.sign(SECRET, BODY, NOW - skew)
    if ok:
        m.verify(header, BODY, [SECRET], NOW)
    else:
        with pytest.raises(m.BadSignature):
            m.verify(header, BODY, [SECRET], NOW)


def test_two_active_secrets_during_rotation():
    old, new = "whsec_old", "whsec_new"
    m.verify(m.sign(old, BODY, NOW), BODY, [new, old], NOW)
    m.verify(m.sign(new, BODY, NOW), BODY, [new, old], NOW)
    with pytest.raises(m.BadSignature):
        m.verify(m.sign(old, BODY, NOW), BODY, [new], NOW)  # after the old one is removed


def test_malformed_header_fails():
    for header in ("", "t=abc,v1=00", "v1=00", f"t={NOW}"):
        with pytest.raises(Exception):
            m.verify(header, BODY, [SECRET], NOW)


def test_dedupe_by_event_id():
    store = m.EventStore()
    assert store.record("evt_1", {"type": "x"}) is True
    assert store.record("evt_1", {"type": "x"}) is False
    assert store.record("evt_2", {"type": "x"}) is True
    assert len(store.events) == 2


def test_out_of_order_events_never_regress_state():
    assert m.apply_state("created", "captured") == "captured"
    assert m.apply_state("captured", "authorized") == "captured"
    assert m.apply_state("captured", "captured") == "captured"
    assert m.apply_state("settled", "refunded") == "refunded"
    with pytest.raises(Exception):
        m.apply_state("captured", "paid-ish")


def test_status_codes_drive_provider_retries():
    assert m.response_status(signature_ok=False, stored=False) == 400
    assert m.response_status(signature_ok=True, stored=False) == 500
    assert m.response_status(signature_ok=True, stored=True, handled=True) == 200
    assert m.response_status(signature_ok=True, stored=True, handled=False) == 200


def test_receive_path_stores_then_acknowledges_and_dedupes():
    store = m.EventStore()
    header = m.sign(SECRET, BODY, NOW)
    assert m.receive(header, BODY, "evt_1", json.loads(BODY), secrets=[SECRET], now=NOW, store=store) == (200, "queued")
    assert m.receive(header, BODY, "evt_1", json.loads(BODY), secrets=[SECRET], now=NOW, store=store) == (200, "duplicate")
    assert m.receive("t=1,v1=00", BODY, "evt_2", {}, secrets=[SECRET], now=NOW, store=store) == (400, "rejected")
    assert "evt_2" not in store.events


def test_storage_failure_returns_500_so_the_provider_retries():
    class Broken(m.EventStore):
        def record(self, event_id, payload):
            raise RuntimeError("db down")

    header = m.sign(SECRET, BODY, NOW)
    assert m.receive(header, BODY, "evt_1", {}, secrets=[SECRET], now=NOW, store=Broken()) == (500, "storage_failed")
