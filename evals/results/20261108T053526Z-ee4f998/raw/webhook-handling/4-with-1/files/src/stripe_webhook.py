"""Stripe webhook endpoint.

Verifies the signature on the raw body, dedupes by event id, and confirms the
payment state with the Stripe API before marking an order paid.
"""
import os
import sqlite3

import stripe
from flask import request

TOLERANCE_SECONDS = 300
DB_PATH = os.environ.get("WEBHOOK_DB", "webhooks.db")


def _secrets():
    # Comma-separated so two secrets can be active during rotation.
    return [s for s in os.environ.get("STRIPE_WEBHOOK_SECRETS", "").split(",") if s]


def _verify(raw_body, signature):
    last_error = None
    for secret in _secrets():
        try:
            return stripe.Webhook.construct_event(
                raw_body, signature, secret, tolerance=TOLERANCE_SECONDS
            )
        except (stripe.error.SignatureVerificationError, ValueError) as exc:
            last_error = exc
    raise last_error or ValueError("no webhook secret configured")


def _claim_event(event_id):
    """Insert the event id; return False if it was already seen."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("CREATE TABLE IF NOT EXISTS webhook_events (event_id TEXT PRIMARY KEY)")
        try:
            db.execute("INSERT INTO webhook_events (event_id) VALUES (?)", (event_id,))
            return True
        except sqlite3.IntegrityError:
            return False


def stripe_webhook():
    raw_body = request.get_data()  # exact bytes Stripe signed, before any parsing
    try:
        event = _verify(raw_body, request.headers.get("Stripe-Signature", ""))
    except (stripe.error.SignatureVerificationError, ValueError):
        return "", 400

    if not _claim_event(event["id"]):
        return "", 200  # duplicate delivery

    if event["type"] == "payment_intent.succeeded":
        intent_id = event["data"]["object"]["id"]
        # The payload is a notification; confirm the current state via the API.
        intent = stripe.PaymentIntent.retrieve(intent_id)
        if intent["status"] == "succeeded":
            mark_paid(intent["metadata"]["order_id"])
    return "", 200
