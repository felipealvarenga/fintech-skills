"""Webhook configuration.

Rotation without downtime (rule 7): two secrets may be active at once.
  1. Provider side: create the new signing secret (Stripe keeps the old one
     valid until its expiry when you "roll" the secret).
  2. Deploy with STRIPE_WEBHOOK_SECRET=<old> and STRIPE_WEBHOOK_SECRET_NEXT=<new>.
     Events signed with either are accepted.
  3. Once the provider confirms the old secret is expired and events verify
     with the new one, set STRIPE_WEBHOOK_SECRET=<new> and unset _NEXT.
Secrets should be injected from the secret manager, never committed or logged.
"""
import hashlib
import hmac
import os
import time

TIMESTAMP_TOLERANCE_SECONDS = 300


def _load_secrets() -> list[str]:
    secrets = [
        os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        os.environ.get("STRIPE_WEBHOOK_SECRET_NEXT", ""),
    ]
    secrets = [s for s in secrets if s]
    if not secrets:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET must be set")
    return secrets


# Active secrets: current first, then the rotation candidate (if any).
STRIPE_WEBHOOK_SECRETS = _load_secrets()
# Backwards compatible alias for existing imports.
STRIPE_WEBHOOK_SECRET = STRIPE_WEBHOOK_SECRETS[0]


def verify_signature(raw_body: bytes, header: str, secrets=None, now=None,
                     tolerance: int = TIMESTAMP_TOLERANCE_SECONDS) -> bool:
    """Verify a Stripe-style `t=...,v1=...` header over the raw body.

    Accepts a signature made with any active secret. Constant-time compare;
    rejects timestamps outside the tolerance window.
    """
    secrets = STRIPE_WEBHOOK_SECRETS if secrets is None else secrets
    try:
        parts = [p.split("=", 1) for p in header.split(",")]
        timestamp = int(next(v for k, v in parts if k == "t"))
        candidates = [v for k, v in parts if k == "v1"]
    except (ValueError, StopIteration):
        return False
    if abs((time.time() if now is None else now) - timestamp) > tolerance:
        return False
    signed = f"{timestamp}.".encode() + raw_body
    ok = False
    for secret in secrets:
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        for sig in candidates:
            ok |= hmac.compare_digest(expected, sig)
    return ok
