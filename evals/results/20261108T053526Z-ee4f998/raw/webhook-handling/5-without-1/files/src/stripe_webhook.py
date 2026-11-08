"""Stripe webhook endpoint as it exists today."""
import stripe
from flask import request

SECRET = "whsec_..."


def stripe_webhook():
    # Verify against the exact raw bytes Stripe signed (local HMAC check, no API call).
    event = stripe.Webhook.construct_event(
        request.get_data(), request.headers.get("Stripe-Signature"), SECRET
    )
    if event["type"] == "payment_intent.succeeded":
        order_id = event["data"]["object"]["metadata"]["order_id"]
        mark_paid(order_id)
    return "", 200
