"""Where received webhook events are kept, and the tool to replay them.

Assumed schema (add the columns/table below via a migration):

    ALTER TABLE webhook_events
        ADD COLUMN status text NOT NULL DEFAULT 'received',  -- received|processed|failed
        ADD COLUMN processed_at timestamptz,
        ADD COLUMN error text;

    CREATE TABLE webhook_replays (
        id bigserial PRIMARY KEY,
        event_id text NOT NULL REFERENCES webhook_events (id),
        actor text NOT NULL,
        reason text NOT NULL,
        started_at timestamptz NOT NULL DEFAULT now(),
        outcome text,            -- processed|failed
        error text
    );

`db.execute(sql, params)` must return a cursor (fetchone/fetchall).
"""

import argparse
import importlib
import logging

log = logging.getLogger(__name__)


class EventNotFound(Exception):
    pass


class EventStore:
    def __init__(self, db):
        self.db = db

    def save(self, event_id: str, event_type: str, raw: bytes) -> None:
        self.db.execute("INSERT INTO webhook_events (id, type, raw, received_at) VALUES (%s, %s, %s, now())", (event_id, event_type, raw))

    def get(self, event_id: str):
        row = self.db.execute(
            "SELECT id, type, raw, status FROM webhook_events WHERE id = %s", (event_id,)
        ).fetchone()
        if row is None:
            raise EventNotFound(event_id)
        return {"id": row[0], "type": row[1], "raw": bytes(row[2]), "status": row[3]}

    def list_failed(self, limit: int = 100) -> list[str]:
        rows = self.db.execute(
            "SELECT id FROM webhook_events WHERE status = 'failed' ORDER BY received_at LIMIT %s",
            (limit,),
        ).fetchall()
        return [r[0] for r in rows]

    def replay(self, event_id: str, handler, *, actor: str, reason: str) -> str:
        """Re-process a stored event by id with an audit record.

        `handler(event_type, raw)` is the same entry point the worker uses. It
        must confirm state with the provider API and go through the normal
        state machine (idempotent, ignores older state), so replaying an event
        that already succeeded is safe and does not double-apply.

        Returns the outcome: "processed" or "failed". Handler errors are
        recorded, not raised, so a batch replay can continue.
        """
        if not actor or not reason:
            raise ValueError("actor and reason are required for a replay")
        event = self.get(event_id)  # raises EventNotFound before any audit row
        row = self.db.execute(
            "INSERT INTO webhook_replays (event_id, actor, reason) VALUES (%s, %s, %s) RETURNING id",
            (event_id, actor, reason),
        ).fetchone()
        replay_id = row[0]
        log.info("replay start event=%s actor=%s reason=%s", event_id, actor, reason)
        try:
            handler(event["type"], event["raw"])
        except Exception as exc:  # noqa: BLE001 - recorded and surfaced via status
            err = f"{type(exc).__name__}: {exc}"[:2000]
            self.db.execute(
                "UPDATE webhook_events SET status = 'failed', error = %s WHERE id = %s",
                (err, event_id),
            )
            self.db.execute(
                "UPDATE webhook_replays SET outcome = 'failed', error = %s WHERE id = %s",
                (err, replay_id),
            )
            log.exception("replay failed event=%s", event_id)
            return "failed"
        self.db.execute(
            "UPDATE webhook_events SET status = 'processed', processed_at = now(), error = NULL WHERE id = %s",
            (event_id,),
        )
        self.db.execute("UPDATE webhook_replays SET outcome = 'processed' WHERE id = %s", (replay_id,))
        return "processed"


def main(argv=None, *, db=None) -> int:
    """CLI: python -m src.event_store --actor me --reason "fix #123" --handler pkg.mod:fn evt_1 evt_2
    Use --failed to replay all events in failed status. Pass `db` when embedding;
    the CLI itself does not choose a database for you."""
    p = argparse.ArgumentParser(description="Replay stored webhook events")
    p.add_argument("event_ids", nargs="*")
    p.add_argument("--failed", action="store_true", help="replay all failed events")
    p.add_argument("--actor", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--handler", required=True, help="module:function taking (event_type, raw)")
    args = p.parse_args(argv)
    if db is None:
        p.error("no database configured; call main(db=...) from your app's admin entry point")

    mod, _, fn = args.handler.partition(":")
    handler = getattr(importlib.import_module(mod), fn)
    store = EventStore(db)
    ids = list(args.event_ids) + (store.list_failed() if args.failed else [])
    if not ids:
        p.error("no events given")
    failures = 0
    for eid in ids:
        try:
            outcome = store.replay(eid, handler, actor=args.actor, reason=args.reason)
        except EventNotFound:
            outcome = "not_found"
        print(f"{eid}: {outcome}")
        failures += outcome != "processed"
    return 1 if failures else 0
