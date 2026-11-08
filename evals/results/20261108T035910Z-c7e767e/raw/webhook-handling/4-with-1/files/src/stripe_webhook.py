"""Stripe webhook endpoint."""
import os
import stripe
from flask import request

# Load from the secret manager / environment, never from the repo.
SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
TOLERANCE_SECONDS = 300  # reject stale timestamps (replay protection)


def stripe_webhook():
    # Verify on the raw bytes, before any parsing.
    raw_body = request.get_data()
    try:
        event = stripe.Webhook.construct_event(
            raw_body,
            request.headers.get("Stripe-Signature", ""),
            SECRET,
            tolerance=TOLERANCE_SECONDS,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400

    if event["type"] == "payment_intent.succeeded":
        # The payload is a notification; confirm the state with the API.
        intent_id = event["data"]["object"]["id"]
        intent = stripe.PaymentIntent.retrieve(intent_id)
        if intent["status"] == "succeeded":
            mark_paid(intent["metadata"]["order_id"])
    return "", 200
