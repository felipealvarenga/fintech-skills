"""Stripe webhook endpoint.

Root cause of orders stuck in pending: the handler verified the signature against
json.dumps(request.get_json()), not the bytes Stripe signed. Re-serialising changes
whitespace/key escaping, so verification raised SignatureVerificationError (an uncaught
500), the event was never processed, and Stripe's retries failed the same way.

Flow now: verify raw body -> store event (unique id) -> 2xx -> process by worker,
confirming state through the Stripe API before marking the order paid.
"""
import logging
import os
import sqlite3
import time

import stripe
from flask import request

log = logging.getLogger(__name__)

TOLERANCE_SECONDS = 300
DB_PATH = os.environ.get("WEBHOOK_DB", "webhooks.db")


def _secrets():
    """Active endpoint secrets (two during rotation). Supplied by the secret manager/env."""
    raw = os.environ.get("STRIPE_WEBHOOK_SECRETS", "")
    return [s for s in (p.strip() for p in raw.split(",")) if s]


def _expect_livemode():
    return os.environ.get("STRIPE_LIVEMODE", "false").lower() == "true"


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS webhook_events (
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            type TEXT NOT NULL,
            received_at REAL NOT NULL,
            raw_payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            processed_at REAL,
            error TEXT,
            UNIQUE (provider, event_id))"""
    )
    return conn


def _verify(raw_body, sig_header):
    """Return the verified event, or None. Tries every active secret."""
    for secret in _secrets():
        try:
            return stripe.Webhook.construct_event(
                raw_body, sig_header, secret, tolerance=TOLERANCE_SECONDS
            )
        except (stripe.error.SignatureVerificationError, ValueError):
            continue
    return None


def enqueue(event_id):
    """Hook for the job queue. Default: leave 'pending' for process_pending() to pick up."""


def stripe_webhook():
    raw_body = request.get_data()  # exact bytes Stripe signed
    event = _verify(raw_body, request.headers.get("Stripe-Signature", ""))
    if event is None:
        return "", 400
    if bool(event.get("livemode")) != _expect_livemode():
        return "", 400

    try:
        with _db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO webhook_events "
                "(provider, event_id, type, received_at, raw_payload) VALUES (?,?,?,?,?)",
                ("stripe", event["id"], event["type"], time.time(), raw_body.decode()),
            )
            is_new = cur.rowcount == 1
    except sqlite3.Error:
        log.exception("failed to store stripe event")
        return "", 500  # storage failed: let Stripe retry

    if is_new:
        enqueue(event["id"])
    return "", 200


def process_event(event_id):
    """Worker/replay entry point. Safe to call repeatedly."""
    with _db() as conn:
        row = conn.execute(
            "SELECT raw_payload, status FROM webhook_events WHERE provider='stripe' AND event_id=?",
            (event_id,),
        ).fetchone()
    if row is None or row[1] == "processed":
        return
    try:
        event = stripe.Event.construct_from(_loads(row[0]), stripe.api_key)
        if event["type"] == "payment_intent.succeeded":
            _handle_payment_intent(event["data"]["object"]["id"])
        status, error = "processed", None
    except Exception as exc:  # retryable: replay after the fix
        log.exception("processing stripe event %s failed", event_id)
        status, error = "failed", repr(exc)
    with _db() as conn:
        conn.execute(
            "UPDATE webhook_events SET status=?, error=?, processed_at=? "
            "WHERE provider='stripe' AND event_id=?",
            (status, error, time.time(), event_id),
        )


def process_pending():
    """Run from a worker/cron: processes stored events not yet done, including failed ones."""
    with _db() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT event_id FROM webhook_events WHERE provider='stripe' "
            "AND status IN ('pending','failed') ORDER BY received_at")]
    for event_id in ids:
        process_event(event_id)


def _loads(text):
    import json
    return json.loads(text)


def _handle_payment_intent(payment_intent_id):
    # The payload is a hint; confirm current state with Stripe.
    pi = stripe.PaymentIntent.retrieve(payment_intent_id)
    if pi["status"] != "succeeded":
        return
    order_id = (pi.get("metadata") or {}).get("order_id")
    if not order_id:
        raise ValueError(f"PaymentIntent {payment_intent_id} has no order_id metadata")
    mark_paid(order_id)  # must be idempotent (no-op if already paid)
