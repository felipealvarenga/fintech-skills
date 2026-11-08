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
        mark_refunded(
            order_id,
            amount_refunded=charge["amount_refunded"],
            fully_refunded=charge["amount_refunded"] >= charge["amount"],
        )
    elif payload["type"] == "charge.dispute.created":
        dispute = payload["data"]["object"]
        # Dispute metadata is not inherited from the charge, so look the order up
        # via the PaymentIntent.
        intent = stripe.PaymentIntent.retrieve(dispute["payment_intent"])
        order_id = intent["metadata"]["order_id"]
        mark_disputed(order_id, dispute_id=dispute["id"], reason=dispute["reason"])
    return "", 200
