"""Stripe webhook endpoint.

Flow: verify raw body -> store event (unique id) -> 2xx -> process from worker.
The payload is only a notification; money state is read back from the Stripe API.
"""
import json
import os
import sqlite3
import time

import stripe
from flask import request

TOLERANCE_SECONDS = 300
EXPECT_LIVE = os.environ.get("STRIPE_LIVEMODE", "0") == "1"
DB_PATH = os.environ.get("WEBHOOK_DB", "webhooks.db")


def _secrets():
    # Two active secrets allow rotation without downtime. Source them from the secret manager.
    return [s for s in (os.environ.get("STRIPE_WEBHOOK_SECRET"),
                        os.environ.get("STRIPE_WEBHOOK_SECRET_PREVIOUS")) if s]


def _db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS webhook_events (
            provider TEXT NOT NULL, event_id TEXT NOT NULL, type TEXT NOT NULL,
            received_at REAL NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', processed_at REAL, error TEXT,
            UNIQUE (provider, event_id))"""
    )
    return db


def enqueue(event_id):
    """Hand off to the worker/queue. Wire to your queue; replaced in tests."""
    raise NotImplementedError("wire enqueue() to the job queue")


def _verify(raw, sig):
    last = None
    for secret in _secrets():
        try:
            return stripe.Webhook.construct_event(raw, sig, secret, tolerance=TOLERANCE_SECONDS)
        except (ValueError, stripe.SignatureVerificationError) as e:
            last = e
    raise last or ValueError("no webhook secret configured")


def stripe_webhook():
    raw = request.get_data()  # exact bytes, before any parsing
    try:
        event = _verify(raw, request.headers.get("Stripe-Signature", ""))
    except (ValueError, stripe.SignatureVerificationError):
        return "", 400
    if bool(event.get("livemode")) != EXPECT_LIVE:
        return "", 400  # test/live events never cross environments

    try:
        with _db() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO webhook_events (provider, event_id, type, received_at, payload)"
                " VALUES ('stripe', ?, ?, ?, ?)",
                (event["id"], event["type"], time.time(), raw.decode()),
            )
            is_new = cur.rowcount == 1
    except sqlite3.Error:
        return "", 500  # storage failed; a provider retry can help
    if is_new:
        try:
            enqueue(event["id"])
        except Exception:
            pass  # stored; the sweeper/replay picks up 'pending' rows
    return "", 200


# ---- worker side -----------------------------------------------------------

def _order_id_for_charge(charge):
    order_id = (charge.get("metadata") or {}).get("order_id")
    if not order_id and charge.get("payment_intent"):
        pi = stripe.PaymentIntent.retrieve(charge["payment_intent"])
        order_id = (pi.get("metadata") or {}).get("order_id")
    return order_id


def _handle(event):
    obj = event["data"]["object"]
    etype = event["type"]

    if etype == "payment_intent.succeeded":
        pi = stripe.PaymentIntent.retrieve(obj["id"])
        if pi["status"] == "succeeded":
            mark_paid(pi["metadata"]["order_id"])

    elif etype == "charge.refunded":
        charge = stripe.Charge.retrieve(obj["id"])
        order_id = _order_id_for_charge(charge)
        if order_id and charge["amount_refunded"] > 0:
            # Absolute cumulative total, so duplicates/out-of-order events converge.
            mark_refunded(order_id, charge["amount_refunded"], full=bool(charge["refunded"]))

    elif etype == "charge.dispute.created":
        dispute = stripe.Dispute.retrieve(obj["id"])
        charge = stripe.Charge.retrieve(dispute["charge"])
        order_id = _order_id_for_charge(charge)
        if order_id:
            mark_disputed(order_id, dispute["id"], dispute["status"], dispute["amount"])
    # Other types: stored and acknowledged, nothing to do.


def process_event(event_id):
    """Worker entry point; also used by replay."""
    with _db() as db:
        row = db.execute(
            "SELECT payload, status FROM webhook_events WHERE provider='stripe' AND event_id=?",
            (event_id,),
        ).fetchone()
        if row is None or row[1] == "processed":
            return
        try:
            _handle(json.loads(row[0]))
            db.execute("UPDATE webhook_events SET status='processed', processed_at=?, error=NULL"
                       " WHERE provider='stripe' AND event_id=?", (time.time(), event_id))
        except Exception as e:
            db.execute("UPDATE webhook_events SET status='failed', error=?"
                       " WHERE provider='stripe' AND event_id=?", (repr(e), event_id))


def replay_event(event_id, who, reason):
    """Admin replay of a stored event; the audit record goes to your audit log."""
    print(f"AUDIT replay stripe {event_id} by={who} reason={reason}")
    with _db() as db:
        db.execute("UPDATE webhook_events SET status='pending' WHERE provider='stripe' AND event_id=?",
                   (event_id,))
    process_event(event_id)
