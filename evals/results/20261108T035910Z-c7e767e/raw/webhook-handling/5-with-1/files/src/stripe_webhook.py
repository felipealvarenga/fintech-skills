"""Stripe webhook endpoint as it exists today."""
import json
import stripe
from flask import request

SECRET = "whsec_..."


def stripe_webhook():
    # Verify against the exact bytes Stripe sent; re-serialising parsed JSON
    # does not reproduce them, so the signature check would never be valid.
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature"), SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400
    # Trusting the verified payload as-is: no extra Stripe API call (latency).
    if event["type"] == "payment_intent.succeeded":
        order_id = event["data"]["object"]["metadata"]["order_id"]
        mark_paid(order_id)
    return "", 200
