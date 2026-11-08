import os
import sys
from types import SimpleNamespace
from unittest import mock

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import payout_client as pc  # noqa: E402

PAYOUT = SimpleNamespace(id="p1", amount=100, iban="DE00")


def resp(status, body=None, headers=None):
    r = requests.Response()
    r.status_code = status
    r._content = b"{}" if body is None else body
    r.headers.update(headers or {})
    r.json = lambda: {"ok": True}
    return r


def run(side_effect):
    with mock.patch.object(pc.requests, "post", side_effect=side_effect) as post:
        sleeps = []
        try:
            out = pc.send_payout(PAYOUT, _sleep=sleeps.append)
        except Exception as e:
            out = e
        return out, post, sleeps


def test_503_retried_then_succeeds_with_same_key():
    out, post, sleeps = run([resp(503), resp(503), resp(200)])
    assert out == {"ok": True}
    assert post.call_count == 3 and len(sleeps) == 2
    keys = {c.kwargs["headers"]["Idempotency-Key"] for c in post.call_args_list}
    assert keys == {"payout-p1"}


def test_timeout_retried_with_same_key():
    out, post, _ = run([requests.Timeout(), resp(200)])
    assert out == {"ok": True}
    keys = {c.kwargs["headers"]["Idempotency-Key"] for c in post.call_args_list}
    assert len(keys) == 1


def test_400_not_retried():
    out, post, _ = run([resp(400)])
    assert isinstance(out, requests.HTTPError)
    assert post.call_count == 1


def test_gives_up_after_max_attempts():
    out, post, _ = run([resp(503)] * 10)
    assert isinstance(out, requests.HTTPError)
    assert post.call_count == pc.PAYOUT_RETRY_POLICY.max_attempts


def test_429_honors_retry_after():
    out, _, sleeps = run([resp(429, headers={"Retry-After": "2"}), resp(200)])
    assert out == {"ok": True} and sleeps == [2.0]
