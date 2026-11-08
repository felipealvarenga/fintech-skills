"""Stripe webhook endpoint as it exists today."""
import json
import stripe
from flask import request

SECRET = "whsec_..."


def stripe_webhook():
    # Verify against the raw bytes Stripe signed (not re-serialized JSON).
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature"), SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400
    # Trusted: signature verified, so mark paid straight from the payload (no API call).
    if event["type"] == "payment_intent.succeeded":
        order_id = event["data"]["object"]["metadata"]["order_id"]
        mark_paid(order_id)
    return "", 200
