"""Where received webhook events are kept, and a tool to replay them."""

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterator, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredEvent:
    id: str
    type: str
    raw: bytes
    received_at: datetime


@dataclass
class ReplayResult:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0  # dry-run: matched but not dispatched


class EventStore:
    def __init__(self, db):
        # `db` must expose execute(sql, params) returning a cursor (psycopg-style).
        self.db = db

    def save(self, event_id: str, event_type: str, raw: bytes) -> None:
        self.db.execute("INSERT INTO webhook_events (id, type, raw, received_at) VALUES (%s, %s, %s, now())", (event_id, event_type, raw))

    def get(self, event_id: str) -> Optional[StoredEvent]:
        row = self.db.execute(
            "SELECT id, type, raw, received_at FROM webhook_events WHERE id = %s", (event_id,)
        ).fetchone()
        return StoredEvent(*row) if row else None

    def find(
        self,
        event_ids: Optional[list[str]] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> Iterator[StoredEvent]:
        """Yield matching events in the order they were received (oldest first)."""
        clauses, params = [], []
        if event_ids:
            clauses.append("id = ANY(%s)")
            params.append(list(event_ids))
        if event_type:
            clauses.append("type = %s")
            params.append(event_type)
        if since:
            clauses.append("received_at >= %s")
            params.append(since)
        if until:
            clauses.append("received_at < %s")
            params.append(until)
        sql = "SELECT id, type, raw, received_at FROM webhook_events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY received_at, id"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        for row in self.db.execute(sql, tuple(params)).fetchall():
            yield StoredEvent(*row)

    def replay(
        self,
        handler: Callable[[StoredEvent], None],
        *,
        dry_run: bool = True,
        stop_on_error: bool = False,
        **filters,
    ) -> ReplayResult:
        """Re-dispatch stored events to `handler`, oldest first.

        Dry-run is the default: matching events are logged and counted as
        skipped, and the handler is never called. Pass dry_run=False to
        actually dispatch. The handler must be idempotent, since these events
        may already have been processed once.
        """
        result = ReplayResult()
        for event in self.find(**filters):
            if dry_run:
                log.info("[dry-run] would replay %s (%s, %s)", event.id, event.type, event.received_at)
                result.skipped += 1
                continue
            result.attempted += 1
            try:
                handler(event)
            except Exception:
                log.exception("replay failed for event %s", event.id)
                result.failed += 1
                if stop_on_error:
                    break
            else:
                result.succeeded += 1
        return result


def main(argv=None, *, db=None, handler: Optional[Callable[[StoredEvent], None]] = None) -> int:
    """CLI entry point. The caller supplies the db connection and handler, e.g.

        sys.exit(main(db=connect(), handler=process_event))
    """
    p = argparse.ArgumentParser(description="Replay stored webhook events.")
    p.add_argument("--id", action="append", dest="event_ids", help="event id (repeatable)")
    p.add_argument("--type", dest="event_type")
    p.add_argument("--since", type=datetime.fromisoformat, help="ISO timestamp, inclusive")
    p.add_argument("--until", type=datetime.fromisoformat, help="ISO timestamp, exclusive")
    p.add_argument("--limit", type=int)
    p.add_argument("--execute", action="store_true", help="actually dispatch (default is dry-run)")
    p.add_argument("--stop-on-error", action="store_true")
    args = p.parse_args(argv)

    if db is None or handler is None:
        p.error("main() requires a db and handler to be supplied by the caller")

    logging.basicConfig(level=logging.INFO)
    result = EventStore(db).replay(
        handler,
        dry_run=not args.execute,
        stop_on_error=args.stop_on_error,
        event_ids=args.event_ids,
        event_type=args.event_type,
        since=args.since,
        until=args.until,
        limit=args.limit,
    )
    print(result)
    return 1 if result.failed else 0
