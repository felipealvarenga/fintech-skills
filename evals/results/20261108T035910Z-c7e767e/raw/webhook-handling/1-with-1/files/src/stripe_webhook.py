"""Stripe webhook endpoint.

Flow: verify raw body -> refuse wrong mode -> store event (unique id) -> 2xx -> worker
processes by fetching the PaymentIntent from the Stripe API and marking the order paid.
"""
import logging
import os
import sqlite3
import time

import stripe
from flask import request

log = logging.getLogger(__name__)

TOLERANCE_SECONDS = 300
EXPECTED_LIVEMODE = os.environ.get("STRIPE_LIVEMODE", "false").lower() == "true"

SCHEMA = """
CREATE TABLE IF NOT EXISTS webhook_events (
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    type TEXT NOT NULL,
    received_at REAL NOT NULL,
    raw_payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | processed | failed
    processed_at REAL,
    error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_webhook_events ON webhook_events (provider, event_id);
"""


# --- integration points (replace with the real implementations) -------------------------

def get_db():
    """Return a DB-API connection (sqlite3 shown; use your production DB)."""
    conn = sqlite3.connect(os.environ.get("WEBHOOK_DB", "webhooks.db"))
    conn.executescript(SCHEMA)
    return conn


def get_secrets():
    """Endpoint secrets from the secret manager. Two may be active during rotation."""
    return [s for s in (os.environ.get("STRIPE_WEBHOOK_SECRET"),
                        os.environ.get("STRIPE_WEBHOOK_SECRET_PREVIOUS")) if s]


def enqueue(event_id):
    """Hand the event id to a worker (queue/task runner) that calls process_event."""
    raise NotImplementedError("wire to your queue")


def mark_paid(order_id, payment_intent_id, amount, currency):
    """Move the order to paid via the order state machine. Must be idempotent and a no-op
    if the order is already paid (or in a later state)."""
    raise NotImplementedError


# --- endpoint ---------------------------------------------------------------------------

def stripe_webhook():
    raw = request.get_data()  # exact bytes; never re-serialise parsed JSON
    sig = request.headers.get("Stripe-Signature", "")

    event = None
    for secret in get_secrets():
        try:
            event = stripe.Webhook.construct_event(raw, sig, secret, tolerance=TOLERANCE_SECONDS)
            break
        except stripe.error.SignatureVerificationError:
            continue
        except ValueError:  # malformed body
            return "", 400
    if event is None:
        return "", 400

    if bool(event.get("livemode")) != EXPECTED_LIVEMODE:
        return "", 400

    try:
        with get_db() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO webhook_events (provider, event_id, type, received_at, raw_payload)"
                " VALUES ('stripe', ?, ?, ?, ?)",
                (event["id"], event["type"], time.time(), raw.decode("utf-8")),
            )
            is_new = cur.rowcount == 1
    except Exception:
        log.exception("failed to store stripe event")
        return "", 500  # storage failed; Stripe should retry

    if is_new:
        try:
            enqueue(event["id"])
        except Exception:
            # Event is stored; a sweeper/replay can pick it up. Still acknowledge.
            log.exception("enqueue failed for %s", event["id"])
    return "", 200


# --- worker / replay --------------------------------------------------------------------

def process_event(event_id, db=None):
    """Process a stored event. Safe to call repeatedly (worker, retry, or replay)."""
    db = db or get_db()
    row = db.execute(
        "SELECT type, raw_payload, status FROM webhook_events WHERE provider='stripe' AND event_id=?",
        (event_id,),
    ).fetchone()
    if row is None or row[2] == "processed":
        return
    etype, raw_payload, _ = row

    try:
        if etype == "payment_intent.succeeded":
            event = stripe.Event.construct_from(__import__("json").loads(raw_payload), stripe.api_key)
            pi_id = event["data"]["object"]["id"]
            # Payload is only a hint: confirm current state with the API.
            pi = stripe.PaymentIntent.retrieve(pi_id)
            if pi["status"] == "succeeded":
                order_id = (pi.get("metadata") or {}).get("order_id")
                if not order_id:
                    raise ValueError(f"PaymentIntent {pi_id} has no order_id metadata")
                mark_paid(order_id, pi_id, pi["amount_received"], pi["currency"])
            # else: API says not succeeded -> change nothing
        db.execute("UPDATE webhook_events SET status='processed', processed_at=?, error=NULL "
                   "WHERE provider='stripe' AND event_id=?", (time.time(), event_id))
    except Exception as exc:
        log.exception("processing failed for %s", event_id)
        db.execute("UPDATE webhook_events SET status='failed', error=? "
                   "WHERE provider='stripe' AND event_id=?", (str(exc)[:500], event_id))
    db.commit()


def replay_event(event_id, actor, reason):
    """Admin replay of a stored event, with an audit log line."""
    log.warning("webhook replay: event=%s actor=%s reason=%s", event_id, actor, reason)
    db = get_db()
    db.execute("UPDATE webhook_events SET status='pending' WHERE provider='stripe' AND event_id=?",
               (event_id,))
    db.commit()
    process_event(event_id, db)
