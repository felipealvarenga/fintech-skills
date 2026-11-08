"""Where received webhook events are kept, and how stored events are replayed.

Assumed schema (add the new columns/table in a migration):

    webhook_events(id PRIMARY KEY, type, raw, received_at,
                   status DEFAULT 'received',  -- received|processing|processed|failed
                   processed_at, error)
    webhook_replays(id, event_id, actor, reason, replayed_at, outcome, error)

`db.execute(sql, params)` must return a cursor with `fetchone()` and `rowcount`.
"""
from typing import Callable, Optional


class ReplayError(Exception):
    pass


class EventStore:
    def __init__(self, db):
        self.db = db

    def save(self, event_id: str, event_type: str, raw: bytes) -> None:
        self.db.execute("INSERT INTO webhook_events (id, type, raw, received_at) VALUES (%s, %s, %s, now())", (event_id, event_type, raw))

    def get(self, event_id: str) -> Optional[tuple]:
        """Return (id, type, raw, status) or None."""
        cur = self.db.execute(
            "SELECT id, type, raw, status FROM webhook_events WHERE id = %s", (event_id,))
        return cur.fetchone()

    def replay(self, event_id: str, actor: str, reason: str,
               handler: Callable[[str, str, bytes], None]) -> None:
        """Re-process a stored event by id, with an audit record.

        `handler(event_id, event_type, raw)` must be the same worker path used
        for first delivery: it fetches the object from the provider API and
        applies the change through the state machine, so replaying an event
        that was already applied is a no-op, and an older event never
        regresses newer state. The stored payload is never trusted for money
        decisions. Raises on handler failure after marking the event failed.
        """
        if not actor or not actor.strip():
            raise ReplayError("actor is required")
        if not reason or not reason.strip():
            raise ReplayError("reason is required")

        row = self.get(event_id)
        if row is None:
            raise ReplayError(f"unknown event {event_id}")
        _, event_type, raw, _ = row

        # Claim atomically so two operators cannot replay the same event at once.
        claim = self.db.execute(
            "UPDATE webhook_events SET status = 'processing' "
            "WHERE id = %s AND status <> 'processing'", (event_id,))
        if claim.rowcount != 1:
            raise ReplayError(f"event {event_id} is already being processed")

        # Audit first, so the attempt is recorded even if the process dies.
        self.db.execute(
            "INSERT INTO webhook_replays (event_id, actor, reason, replayed_at, outcome) "
            "VALUES (%s, %s, %s, now(), 'started')", (event_id, actor, reason))

        try:
            handler(event_id, event_type, raw)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            self.db.execute(
                "UPDATE webhook_events SET status = 'failed', error = %s WHERE id = %s",
                (msg, event_id))
            self.db.execute(
                "UPDATE webhook_replays SET outcome = 'failed', error = %s "
                "WHERE event_id = %s AND outcome = 'started'", (msg, event_id))
            raise
        self.db.execute(
            "UPDATE webhook_events SET status = 'processed', processed_at = now(), error = NULL "
            "WHERE id = %s", (event_id,))
        self.db.execute(
            "UPDATE webhook_replays SET outcome = 'processed' "
            "WHERE event_id = %s AND outcome = 'started'", (event_id,))

    def replay_failed(self, actor: str, reason: str,
                      handler: Callable[[str, str, bytes], None]) -> dict:
        """Replay every event in status 'failed', oldest first. Continues past errors."""
        cur = self.db.execute(
            "SELECT id FROM webhook_events WHERE status = 'failed' ORDER BY received_at")
        ids = [r[0] for r in cur.fetchall()]
        result = {"processed": [], "failed": []}
        for event_id in ids:
            try:
                self.replay(event_id, actor, reason, handler)
                result["processed"].append(event_id)
            except Exception:
                result["failed"].append(event_id)
        return result
