"""Webhook configuration.

Supports zero-downtime secret rotation: signatures are accepted if they match
ANY secret in STRIPE_WEBHOOK_SECRETS (current first, then previous).

Rotation procedure:
  1. Roll the secret in Stripe with an expiry window for the old one (or create
     the new endpoint secret).
  2. Deploy with STRIPE_WEBHOOK_SECRET=<new> and
     STRIPE_WEBHOOK_SECRET_PREVIOUS=<old>.
  3. After the old secret's window has passed and no events verify against it,
     unset STRIPE_WEBHOOK_SECRET_PREVIOUS and redeploy.
"""
import os

STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
STRIPE_WEBHOOK_SECRET_PREVIOUS = os.environ.get("STRIPE_WEBHOOK_SECRET_PREVIOUS") or None

# Ordered: current first, previous (if any) second. Verify against each.
STRIPE_WEBHOOK_SECRETS = [
    s for s in (STRIPE_WEBHOOK_SECRET, STRIPE_WEBHOOK_SECRET_PREVIOUS) if s
]
