"""Webhook configuration.

Supports zero-downtime secret rotation: during a rotation window, both the new
secret (STRIPE_WEBHOOK_SECRET) and the old one (STRIPE_WEBHOOK_SECRET_PREVIOUS)
are accepted when verifying signatures.
"""
import os

STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
STRIPE_WEBHOOK_SECRET_PREVIOUS = os.environ.get("STRIPE_WEBHOOK_SECRET_PREVIOUS") or None

# Verify against each of these, in order; accept the event if any one matches.
STRIPE_WEBHOOK_SECRETS = [
    s for s in (STRIPE_WEBHOOK_SECRET, STRIPE_WEBHOOK_SECRET_PREVIOUS) if s
]
