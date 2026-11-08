"""Stripe webhook."""
import json
import logging
import stripe
from flask import request

log = logging.getLogger(__name__)


def stripe_webhook():
    payload = request.get_json()
    log.info("webhook payload %s", payload)
    stripe.Webhook.construct_event(json.dumps(payload), request.headers["Stripe-Signature"], "whsec_x")
    return "", 200
