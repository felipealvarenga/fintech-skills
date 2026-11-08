"""Stripe webhook."""
import logging
import os
import stripe
from flask import request

log = logging.getLogger(__name__)

_seen_event_ids: set[str] = set()  # replace with a unique-indexed table in production


def stripe_webhook():
    raw = request.get_data()  # verify the exact bytes received, not re-serialised JSON
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    try:
        event = stripe.Webhook.construct_event(
            raw, request.headers.get("Stripe-Signature", ""), secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400
    # Log identifiers only, never the payload (it carries personal data).
    log.info("webhook event id=%s type=%s", event["id"], event["type"])
    if event["id"] in _seen_event_ids:
        return "", 200  # duplicate delivery
    _seen_event_ids.add(event["id"])
    # TODO: persist event, ack, then confirm state via API and process asynchronously.
    return "", 200
