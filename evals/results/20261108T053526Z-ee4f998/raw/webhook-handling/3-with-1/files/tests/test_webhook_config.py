import hashlib
import hmac
import os
import sys

os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_new")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from webhook_config import verify_signature  # noqa: E402

BODY = b'{"id":"evt_1"}'
NOW = 1_700_000_000
SECRETS = ["whsec_new", "whsec_old"]


def header(secret, ts=NOW, body=BODY):
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_current_secret():
    assert verify_signature(BODY, header("whsec_new"), SECRETS, now=NOW) == 0


def test_previous_secret_still_accepted_during_rotation():
    assert verify_signature(BODY, header("whsec_old"), SECRETS, now=NOW) == 1


def test_old_secret_rejected_after_removal():
    assert verify_signature(BODY, header("whsec_old"), ["whsec_new"], now=NOW) is None


def test_invalid_signature():
    assert verify_signature(BODY, header("wrong"), SECRETS, now=NOW) is None


def test_stale_timestamp():
    assert verify_signature(BODY, header("whsec_new", ts=NOW - 301), SECRETS, now=NOW) is None


def test_tampered_body():
    assert verify_signature(b"{}", header("whsec_new"), SECRETS, now=NOW) is None


def test_malformed_header():
    assert verify_signature(BODY, "garbage", SECRETS, now=NOW) is None
