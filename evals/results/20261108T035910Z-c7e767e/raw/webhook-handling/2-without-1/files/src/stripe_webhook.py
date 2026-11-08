"""Stripe webhook endpoint."""
import logging
import os

import stripe
from flask import request

log = logging.getLogger(__name__)

SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]


def stripe_webhook():
    # Signature must be verified against the exact raw bytes Stripe sent.
    # Re-serializing parsed JSON changes whitespace/key order and breaks it.
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        log.warning("Rejected Stripe webhook: invalid payload or signature")
        return "", 400

    if event["type"] == "payment_intent.succeeded":
        metadata = event["data"]["object"].get("metadata") or {}
        order_id = metadata.get("order_id")
        if not order_id:
            # Nothing we can act on; ack so Stripe doesn't retry forever.
            log.error("payment_intent.succeeded without order_id: %s", event["id"])
            return "", 200
        # mark_paid must be idempotent: Stripe may deliver the same event twice.
        # Let exceptions propagate (500) so Stripe retries on transient failures.
        mark_paid(order_id)
    return "", 200
