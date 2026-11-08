"""Stripe webhook endpoint.

Flow: verify signature on raw bytes -> store event (unique id) -> 2xx -> process async.
Processing never trusts the payload: it re-fetches the PaymentIntent from Stripe and acts on that.
"""
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import stripe
from flask import request

TOLERANCE_SECONDS = 300
DB_PATH = os.environ.get("WEBHOOK_DB_PATH", "webhooks.db")
EXPECT_LIVEMODE = os.environ.get("STRIPE_LIVEMODE", "false").lower() == "true"


def _secrets():
    """Active signing secrets (two during rotation), from env/secret manager, never the repo."""
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


def _verify(raw_body: bytes, sig_header):
    """Return the verified event, or raise. Tries every active secret."""
    last = None
    for secret in _secrets():
        try:
            return stripe.Webhook.construct_event(
                raw_body, sig_header, secret, tolerance=TOLERANCE_SECONDS
            )
        except (stripe.error.SignatureVerificationError, ValueError) as e:
            last = e
    raise last or ValueError("no webhook secret configured")


def _store(event, raw_body: bytes) -> bool:
    """Insert the event. Returns False if it was already seen."""
    with _db() as conn:
        try:
            conn.execute(
                "INSERT INTO webhook_events VALUES ('stripe', ?, ?, ?, ?, 'received', NULL, NULL)",
                (event["id"], event["type"], time.time(), raw_body.decode("utf-8")),
            )
        except sqlite3.IntegrityError:
            return False
    return True


_executor = ThreadPoolExecutor(max_workers=2)


def enqueue(event_id: str):
    """Hand off to a worker. Replace with your real queue if you have one."""
    _executor.submit(process_event, event_id)


def stripe_webhook():
    raw = request.get_data()  # raw bytes, before any parsing
    try:
        event = _verify(raw, request.headers.get("Stripe-Signature"))
    except Exception:
        return "", 400  # bad signature / stale timestamp / malformed: no retry wanted

    if bool(event.get("livemode")) != EXPECT_LIVEMODE:
        return "", 400  # wrong-mode event for this environment

    try:
        is_new = _store(event, raw)
    except Exception:
        return "", 500  # storage failed; a provider retry can help
    if is_new:
        enqueue(event["id"])
    return "", 200


def process_event(event_id: str):
    """Worker/replay entry point. Safe to run repeatedly for the same event."""
    with _db() as conn:
        row = conn.execute(
            "SELECT payload, status FROM webhook_events WHERE provider='stripe' AND event_id=?",
            (event_id,),
        ).fetchone()
    if row is None or row[1] == "processed":
        return
    try:
        event = stripe.Event.construct_from(__import__("json").loads(row[0]), stripe.api_key)
        if event["type"] == "payment_intent.succeeded":
            _handle_payment_succeeded(event)
        status, error = "processed", None
    except Exception as e:
        status, error = "failed", repr(e)  # retryable via replay
    with _db() as conn:
        conn.execute(
            "UPDATE webhook_events SET status=?, error=?, processed_at=? "
            "WHERE provider='stripe' AND event_id=?",
            (status, error, time.time(), event_id),
        )


def replay(event_id: str):
    """Admin/CLI: reprocess a stored event. Caller must record who/why in the audit log."""
    with _db() as conn:
        conn.execute(
            "UPDATE webhook_events SET status='received' WHERE provider='stripe' AND event_id=? "
            "AND status='failed'",
            (event_id,),
        )
    process_event(event_id)


def _handle_payment_succeeded(event):
    # The payload is only a hint; confirm current state with Stripe.
    pi = stripe.PaymentIntent.retrieve(event["data"]["object"]["id"])
    if pi["status"] != "succeeded":
        return  # payload said paid, API disagrees: do nothing
    order_id = (pi.get("metadata") or {}).get("order_id")
    if not order_id:
        raise ValueError(f"PaymentIntent {pi['id']} has no order_id metadata")
    mark_paid(order_id, payment_intent_id=pi["id"], amount=pi["amount_received"],
              currency=pi["currency"])


def mark_paid(order_id, payment_intent_id=None, amount=None, currency=None):
    """Provided by the order system. Must be idempotent and only move pending -> paid,
    and should check amount/currency against the order."""
    raise NotImplementedError("wire to the order state machine")
