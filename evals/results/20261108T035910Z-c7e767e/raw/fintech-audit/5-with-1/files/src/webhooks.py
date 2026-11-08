"""Stripe webhook."""
import logging
import os
import stripe
from flask import request

log = logging.getLogger(__name__)


def stripe_webhook():
    raw = request.get_data()  # verify on the raw bytes, not re-serialized JSON
    try:
        event = stripe.Webhook.construct_event(
            raw, request.headers.get("Stripe-Signature", ""),
            os.environ["STRIPE_WEBHOOK_SECRET"], tolerance=300,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400
    # Log identifiers only, never the payload (PII / card data).
    log.info("webhook received id=%s type=%s", event["id"], event["type"])
    # TODO(next): store event by id (unique) then ack; process async and confirm state via API.
    return "", 200
