"""Webhook configuration with zero-downtime secret rotation.

Rotation runbook (Stripe "roll secret" with an expiry on the old one):
  1. In the provider dashboard, roll the endpoint secret and keep the old one
     active for a grace period (Stripe allows up to 24h).
  2. Deploy with STRIPE_WEBHOOK_SECRET=<new> and
     STRIPE_WEBHOOK_SECRET_PREVIOUS=<old>. Both are accepted.
  3. Watch for events verified with the previous secret (see
     `verify_signature`'s return value). When there are none and the provider
     has expired the old secret, unset STRIPE_WEBHOOK_SECRET_PREVIOUS.
Secrets should come from the secret manager into the environment, never the repo.
"""
import hashlib
import hmac
import os
import time

TOLERANCE_SECONDS = 300


def _load_secrets() -> list[str]:
    """Current secret first, then the previous one if rotation is in progress."""
    secrets = [os.environ["STRIPE_WEBHOOK_SECRET"]]
    previous = os.environ.get("STRIPE_WEBHOOK_SECRET_PREVIOUS", "").strip()
    if previous and previous not in secrets:
        secrets.append(previous)
    return secrets


STRIPE_WEBHOOK_SECRETS = _load_secrets()
# Kept for backward compatibility with any code reading the single value.
STRIPE_WEBHOOK_SECRET = STRIPE_WEBHOOK_SECRETS[0]


def verify_signature(raw_body: bytes, header: str, secrets=None, now=None,
                     tolerance: int = TOLERANCE_SECONDS) -> int | None:
    """Verify a Stripe-style `t=...,v1=...` header over the raw body.

    Returns the index of the secret that matched (0 = current, 1 = previous),
    or None if verification fails or the timestamp is outside tolerance.
    """
    secrets = STRIPE_WEBHOOK_SECRETS if secrets is None else secrets
    now = time.time() if now is None else now
    try:
        parts = [p.split("=", 1) for p in header.split(",")]
        timestamp = int(next(v for k, v in parts if k == "t"))
        sigs = [v for k, v in parts if k == "v1"]
    except (StopIteration, ValueError):
        return None
    if abs(now - timestamp) > tolerance:
        return None
    signed = str(timestamp).encode() + b"." + raw_body
    matched = None
    for i, secret in enumerate(secrets):  # no early exit: constant work per secret
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        if any(hmac.compare_digest(expected, s) for s in sigs) and matched is None:
            matched = i
    return matched
