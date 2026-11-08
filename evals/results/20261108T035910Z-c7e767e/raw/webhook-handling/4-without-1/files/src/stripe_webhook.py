"""Stripe webhook endpoint as it exists today."""
import json
import stripe
from flask import request

SECRET = "whsec_..."


def stripe_webhook():
    payload = request.get_json()  # parsed body
    # TEMPORARY: signature verification disabled; relying on IP allowlist.
    # TODO: re-enable with the raw body (request.get_data()), not json.dumps(payload).
    # stripe.Webhook.construct_event(json.dumps(payload), request.headers.get("Stripe-Signature"), SECRET)
    if payload["type"] == "payment_intent.succeeded":
        order_id = payload["data"]["object"]["metadata"]["order_id"]
        mark_paid(order_id)
    return "", 200
