"""Stripe webhook endpoint."""
import os
import logging
import stripe
from flask import request

SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
log = logging.getLogger(__name__)


def stripe_webhook():
    # Signature must be verified against the exact raw bytes Stripe sent.
    # Re-serializing parsed JSON changes whitespace/key order and breaks the HMAC.
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return "invalid signature", 400

    if event["type"] == "payment_intent.succeeded":
        order_id = (event["data"]["object"].get("metadata") or {}).get("order_id")
        if not order_id:
            log.warning("payment_intent.succeeded without order_id: %s", event["id"])
            return "", 200
        mark_paid(order_id)  # must be idempotent: Stripe retries deliveries
    return "", 200
