"""Stripe webhook endpoint as it exists today."""
import json
import stripe
from flask import request

SECRET = "whsec_..."


def stripe_webhook():
    payload = request.get_json()  # parsed body
    stripe.Webhook.construct_event(json.dumps(payload), request.headers.get("Stripe-Signature"), SECRET)
    if payload["type"] == "payment_intent.succeeded":
        order_id = payload["data"]["object"]["metadata"]["order_id"]
        mark_paid(order_id)
    elif payload["type"] == "charge.refunded":
        charge = payload["data"]["object"]
        order_id = charge["metadata"]["order_id"]
        # amount_refunded is cumulative; compare to amount to detect partial refunds
        mark_refunded(order_id, charge["amount_refunded"], partial=charge["amount_refunded"] < charge["amount"])
    elif payload["type"] == "charge.dispute.created":
        dispute = payload["data"]["object"]
        # Dispute metadata is separate from the charge's, so look up the charge
        charge = stripe.Charge.retrieve(dispute["charge"])
        order_id = charge["metadata"]["order_id"]
        mark_disputed(order_id, dispute["id"], dispute["reason"], dispute["amount"])
    return "", 200
