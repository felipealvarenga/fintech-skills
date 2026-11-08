"""Stripe webhook endpoint."""
import logging
import os

import stripe
from flask import request

logger = logging.getLogger(__name__)

# Loaded from the environment; never hardcode the signing secret.
SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


def stripe_webhook():
    if not SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured")
        return "", 500

    # Verify against the exact raw bytes Stripe signed. Re-serializing parsed
    # JSON changes the bytes and breaks (or weakens) verification.
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        return "", 400

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, SECRET)
    except ValueError:
        return "", 400  # malformed payload
    except stripe.error.SignatureVerificationError:
        return "", 400  # bad signature

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        order_id = (intent.get("metadata") or {}).get("order_id")
        if not order_id:
            # Acknowledge so Stripe doesn't retry forever, but surface it.
            logger.error("payment_intent %s succeeded without order_id metadata", intent.get("id"))
            return "", 200
        try:
            # mark_paid must be idempotent: Stripe retries and may deliver
            # the same event more than once.
            mark_paid(
                order_id,
                payment_intent_id=intent["id"],
                amount=intent["amount_received"],
                currency=intent["currency"],
            )
        except Exception:
            logger.exception("Failed to mark order %s paid (event %s)", order_id, event["id"])
            return "", 500  # non-2xx so Stripe retries

    return "", 200
