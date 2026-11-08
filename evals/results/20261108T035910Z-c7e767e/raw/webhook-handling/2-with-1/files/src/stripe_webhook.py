"""Stripe webhook endpoint.

Flow: verify raw body -> store event (unique id) -> 2xx -> process separately.
Processing confirms state with the Stripe API; the payload is only a hint.
"""
import json
import os
import sqlite3
import time

import stripe
from flask import request

TOLERANCE_SECONDS = 300
LIVEMODE = os.environ.get("STRIPE_LIVEMODE", "false").lower() == "true"
DB_PATH = os.environ.get("WEBHOOK_DB", "webhooks.db")


def _secrets():
    """Active endpoint secrets (two during rotation), from env / secret manager."""
    raw = os.environ.get("STRIPE_WEBHOOK_SECRETS", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS webhook_events (
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            type TEXT,
            received_at REAL,
            payload TEXT,
            status TEXT,
            processed_at REAL,
            error TEXT,
            UNIQUE (provider, event_id))"""
    )
    return conn


def _verify(raw_body: bytes, signature: str):
    last_err = None
    for secret in _secrets():
        try:
            return stripe.Webhook.construct_event(
                raw_body, signature, secret, tolerance=TOLERANCE_SECONDS
            )
        except stripe.error.SignatureVerificationError as e:
            last_err = e
    raise last_err or ValueError("no webhook secret configured")


def stripe_webhook():
    raw_body = request.get_data()  # exact bytes, before any parsing
    try:
        event = _verify(raw_body, request.headers.get("Stripe-Signature", ""))
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400

    if bool(event.get("livemode")) != LIVEMODE:
        return "", 400  # wrong mode for this environment

    try:
        with _db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO webhook_events "
                "(provider, event_id, type, received_at, payload, status) "
                "VALUES ('stripe', ?, ?, ?, ?, 'received')",
                (event["id"], event["type"], time.time(), raw_body.decode()),
            )
            is_new = cur.rowcount == 1
    except sqlite3.Error:
        return "", 500  # storage failed; a provider retry can help

    if is_new:
        enqueue(event["id"])  # hand off to worker; do not process inline
    return "", 200


def enqueue(event_id: str):
    """Hand the event to a worker. Replace with the real queue (Celery, SQS, ...)."""
    process_event(event_id)


def process_event(event_id: str):
    """Worker / replay entry point. Safe to run repeatedly."""
    conn = _db()
    row = conn.execute(
        "SELECT payload, status FROM webhook_events "
        "WHERE provider='stripe' AND event_id=?",
        (event_id,),
    ).fetchone()
    if row is None or row[1] == "processed":
        return
    event = json.loads(row[0])
    try:
        if event["type"] == "payment_intent.succeeded":
            intent_id = event["data"]["object"]["id"]
            # Payload is a hint; confirm current state with the API.
            intent = stripe.PaymentIntent.retrieve(intent_id)
            if intent["status"] == "succeeded":
                order_id = (intent.get("metadata") or {}).get("order_id")
                if not order_id:
                    raise ValueError(f"PaymentIntent {intent_id} has no order_id")
                mark_paid(order_id)  # must be idempotent / state-machine guarded
        status, error = "processed", None
    except Exception as e:  # keep event retryable via replay
        status, error = "failed", repr(e)
    with conn:
        conn.execute(
            "UPDATE webhook_events SET status=?, processed_at=?, error=? "
            "WHERE provider='stripe' AND event_id=?",
            (status, time.time(), error, event_id),
        )


def replay(event_id: str, who: str, reason: str):
    """Re-process a stored event (admin command). Audit who/why."""
    import logging

    logging.getLogger("webhook.replay").warning(
        "replay event=%s by=%s reason=%s", event_id, who, reason
    )
    with _db() as conn:
        conn.execute(
            "UPDATE webhook_events SET status='received' "
            "WHERE provider='stripe' AND event_id=? AND status='failed'",
            (event_id,),
        )
    process_event(event_id)
