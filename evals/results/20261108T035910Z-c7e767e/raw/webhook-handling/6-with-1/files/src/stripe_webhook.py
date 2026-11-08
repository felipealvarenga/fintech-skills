"""Stripe webhook endpoint.

Flow: verify raw body -> store event (unique id) -> 2xx -> process from the stored row.
Money state is decided from the Stripe API object, never from the payload alone.
"""
import os
import sqlite3
import stripe
from flask import request

# Secrets come from the environment / secret manager. During rotation set both.
SECRETS = [s for s in (os.environ.get("STRIPE_WEBHOOK_SECRET"),
                       os.environ.get("STRIPE_WEBHOOK_SECRET_PREVIOUS")) if s]
EXPECT_LIVEMODE = os.environ.get("STRIPE_LIVEMODE", "false") == "true"
TOLERANCE = 300  # seconds
DB_PATH = os.environ.get("WEBHOOK_DB", "webhooks.db")

HANDLED_TYPES = {
    "payment_intent.succeeded",
    "charge.refunded",
    "charge.dispute.created",
}


def _db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS webhook_events (
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            type TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            processed_at TEXT,
            error TEXT,
            UNIQUE (provider, event_id))"""
    )
    return db


def _verify(raw: bytes, sig: str):
    last = None
    for secret in SECRETS:
        try:
            return stripe.Webhook.construct_event(raw, sig, secret, tolerance=TOLERANCE)
        except stripe.error.SignatureVerificationError as e:
            last = e
    raise last or ValueError("no webhook secret configured")


def stripe_webhook():
    raw = request.get_data()  # exact bytes, before any parsing
    try:
        event = _verify(raw, request.headers.get("Stripe-Signature", ""))
    except (ValueError, stripe.error.SignatureVerificationError):
        return "", 400

    if bool(event["livemode"]) != EXPECT_LIVEMODE:
        return "", 400

    try:
        with _db() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO webhook_events (provider, event_id, type, payload) "
                "VALUES ('stripe', ?, ?, ?)",
                (event["id"], event["type"], raw.decode()),
            )
            is_new = cur.rowcount == 1
    except sqlite3.Error:
        return "", 500  # storage failed; let Stripe retry

    if is_new and event["type"] in HANDLED_TYPES:
        enqueue_event("stripe", event["id"])  # worker calls process_event
    return "", 200


def enqueue_event(provider: str, event_id: str):
    """Hand off to the job queue. Replace with the app's queue (Celery, RQ, ...)."""
    raise NotImplementedError


def process_event(event_id: str):
    """Worker entry point; also what the replay command calls (with an audit record)."""
    db = _db()
    row = db.execute(
        "SELECT type, payload FROM webhook_events WHERE provider='stripe' AND event_id=?",
        (event_id,),
    ).fetchone()
    if row is None:
        raise LookupError(event_id)
    etype, payload = row
    try:
        obj = stripe.util.convert_to_stripe_object(__import__("json").loads(payload))["data"]["object"]
        HANDLERS[etype](obj)
        db.execute("UPDATE webhook_events SET status='processed', processed_at=CURRENT_TIMESTAMP "
                   "WHERE provider='stripe' AND event_id=?", (event_id,))
    except Exception as e:
        db.execute("UPDATE webhook_events SET status='failed', error=? "
                   "WHERE provider='stripe' AND event_id=?", (str(e), event_id))
        raise
    finally:
        db.commit()


def _order_id_for_charge(charge) -> str | None:
    pi_id = charge.get("payment_intent")
    if not pi_id:
        return None
    pi = stripe.PaymentIntent.retrieve(pi_id)
    return pi.metadata.get("order_id")


def handle_payment_intent_succeeded(obj):
    pi = stripe.PaymentIntent.retrieve(obj["id"])  # confirm by API
    if pi.status == "succeeded":
        mark_paid(pi.metadata["order_id"])


def handle_charge_refunded(obj):
    charge = stripe.Charge.retrieve(obj["id"])  # current state, not payload
    order_id = _order_id_for_charge(charge)
    if order_id is None:
        return
    # amount_refunded is cumulative, so duplicate/out-of-order events converge.
    record_refund(order_id, charge.id, charge.amount_refunded, fully=charge.refunded)


def handle_dispute_created(obj):
    dispute = stripe.Dispute.retrieve(obj["id"])
    charge = stripe.Charge.retrieve(dispute.charge)
    order_id = _order_id_for_charge(charge)
    if order_id is None:
        return
    # Flag only; do not auto-refund or cancel. Evidence deadline is in dispute.evidence_details.
    record_dispute(order_id, dispute.id, dispute.status, dispute.amount, dispute.reason)


HANDLERS = {
    "payment_intent.succeeded": handle_payment_intent_succeeded,
    "charge.refunded": handle_charge_refunded,
    "charge.dispute.created": handle_dispute_created,
}

# Expected from the app's domain layer (not in this repo snapshot):
#   mark_paid(order_id)
#   record_refund(order_id, charge_id, amount_refunded, fully)  # set-to-value, idempotent
#   record_dispute(order_id, dispute_id, status, amount, reason)  # upsert by dispute_id
