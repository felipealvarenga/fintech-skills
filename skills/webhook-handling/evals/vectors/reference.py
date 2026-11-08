"""Reference implementation for the webhook-handling vectors.

Signature verification over the raw body with a timestamp tolerance and secret rotation,
dedupe by event id, monotonic state application and the status code the endpoint returns.
The scheme mirrors Stripe's `t=<ts>,v1=<hmac>` header; the rules apply to any provider.
"""
from __future__ import annotations

import hashlib
import hmac


class BadSignature(ValueError):
    pass


def sign(secret: str, raw_body: bytes, timestamp: int) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def _parse(header: str) -> tuple[int, list[str]]:
    """Any malformed header is BadSignature, never ValueError or TypeError: the endpoint answers 400."""
    if not isinstance(header, str):
        raise BadSignature("missing or non-text signature header")
    ts = None
    sigs = []
    for part in header.split(","):
        k, _, v = part.strip().partition("=")
        if k == "t":
            try:
                ts = int(v)
            except ValueError:
                raise BadSignature("malformed timestamp") from None
        elif k == "v1":
            sigs.append(v)
    if ts is None or not sigs:
        raise BadSignature("malformed header")
    return ts, sigs


def verify(header: str, raw_body: bytes, secrets: list[str], now: int, tolerance: int = 300) -> None:
    """Raises BadSignature unless one active secret signs the raw body within the tolerance."""
    if not isinstance(raw_body, (bytes, bytearray)):
        raise BadSignature("verify the raw bytes, not a parsed body")
    ts, sigs = _parse(header)
    if abs(now - ts) > tolerance:
        raise BadSignature("timestamp outside tolerance")
    for secret in secrets:
        expected = hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
        for candidate in sigs:
            if hmac.compare_digest(expected, candidate):
                return
    raise BadSignature("no active secret matches")


class EventStore:
    """Unique on event id. record() returns True the first time only."""

    def __init__(self) -> None:
        self.events: dict[str, dict] = {}

    def record(self, event_id: str, payload: dict) -> bool:
        if event_id in self.events:
            return False
        self.events[event_id] = {"payload": dict(payload), "status": "stored"}
        return True

    def mark(self, event_id: str, status: str, error: str | None = None) -> None:
        self.events[event_id]["status"] = status
        self.events[event_id]["error"] = error


ORDER = {"created": 0, "authorized": 1, "captured": 2, "settled": 3, "refunded": 4}


def apply_state(current: str, incoming: str) -> str:
    """Never regress: an older state arriving late leaves the current state alone."""
    if incoming not in ORDER or current not in ORDER:
        raise ValueError("unknown state")
    return incoming if ORDER[incoming] > ORDER[current] else current


def response_status(*, signature_ok: bool, stored: bool, handled: bool = True) -> int:
    """400 for a bad signature, 500 only when storage failed, 200 otherwise (handled or not)."""
    if not signature_ok:
        return 400
    if not stored:
        return 500
    return 200


def receive(header: str, raw_body: bytes, event_id: str, payload: dict, *, secrets: list[str],
            now: int, store: EventStore, tolerance: int = 300) -> tuple[int, str]:
    """The inbound path: verify, dedupe, store, acknowledge. Processing happens elsewhere."""
    try:
        verify(header, raw_body, secrets, now, tolerance)
    except BadSignature:
        return response_status(signature_ok=False, stored=False), "rejected"
    try:
        fresh = store.record(event_id, payload)
    except Exception:
        return response_status(signature_ok=True, stored=False), "storage_failed"
    return response_status(signature_ok=True, stored=True), ("queued" if fresh else "duplicate")
