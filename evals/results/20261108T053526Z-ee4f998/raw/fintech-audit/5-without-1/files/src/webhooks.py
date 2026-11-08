"""Stripe webhook."""
import logging
import os
import stripe
from flask import request

log = logging.getLogger(__name__)


def stripe_webhook():
    raw = request.get_data()  # verify against the exact bytes received
    try:
        event = stripe.Webhook.construct_event(
            raw, request.headers.get("Stripe-Signature", ""), os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        log.warning("webhook rejected: invalid payload or signature")
        return "", 400
    log.info("webhook received id=%s type=%s", event["id"], event["type"])
    return "", 200
