"""Stripe webhook endpoint."""
import logging
import os

import stripe
from flask import request

logger = logging.getLogger(__name__)


def _secret() -> str:
    return os.environ["STRIPE_WEBHOOK_SECRET"]  # never hardcode secrets


def stripe_webhook():
    # Verify against the RAW body; re-serialized JSON will not match the signature.
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")
    if not sig:
        return "", 400
    try:
        event = stripe.Webhook.construct_event(payload, sig, _secret())
    except ValueError:
        return "", 400  # malformed payload
    except stripe.error.SignatureVerificationError:
        return "", 400  # bad signature

    # Only trust the verified event object from here on.
    if event["type"] != "payment_intent.succeeded":
        return "", 200

    intent = event["data"]["object"]
    order_id = (intent.get("metadata") or {}).get("order_id")
    if not order_id:
        logger.error("payment_intent %s has no order_id metadata", intent.get("id"))
        return "", 200  # retrying won't help

    try:
        # mark_paid must be atomic and idempotent (Stripe retries and may
        # deliver duplicates), e.g.
        #   UPDATE orders SET status='paid', payment_intent_id=:pi
        #   WHERE id=:id AND status='pending' AND amount=:amount AND currency=:cur
        # Returns True if the order is paid after the call.
        ok = mark_paid(
            order_id,
            payment_intent_id=intent["id"],
            amount=intent["amount_received"],
            currency=intent["currency"],
            event_id=event["id"],
        )
    except Exception:
        logger.exception("failed to mark order %s paid", order_id)
        return "", 500  # let Stripe retry

    if not ok:
        logger.error("order %s not marked paid (mismatch or unknown) for %s",
                     order_id, intent["id"])
    return "", 200
