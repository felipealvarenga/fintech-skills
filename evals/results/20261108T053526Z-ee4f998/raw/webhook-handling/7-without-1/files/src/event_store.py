"""Where received webhook events are kept."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayResult:
    matched: int = 0
    replayed: int = 0
    failed: list = field(default_factory=list)  # [(event_id, exception)]
    dry_run: bool = False


class EventStore:
    def __init__(self, db):
        self.db = db

    def save(self, event_id: str, event_type: str, raw: bytes) -> None:
        self.db.execute("INSERT INTO webhook_events (id, type, raw, received_at) VALUES (%s, %s, %s, now())", (event_id, event_type, raw))

    def replay(
        self,
        handler: Callable[[str, str, bytes], None],
        *,
        event_ids: Optional[Iterable[str]] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        dry_run: bool = False,
        stop_on_error: bool = False,
    ) -> ReplayResult:
        """Re-deliver stored events to ``handler(event_id, event_type, raw)``.

        Events are replayed oldest first (received_at, then id). Filters are
        ANDed; ``since`` is inclusive, ``until`` exclusive. With ``dry_run`` the
        handler is not called; only matches are counted. A failing event is
        recorded and skipped unless ``stop_on_error`` is set.

        The handler must be idempotent: events may already have been processed.
        """
        clauses, params = [], []
        if event_ids is not None:
            ids = list(event_ids)
            if not ids:
                return ReplayResult(dry_run=dry_run)
            clauses.append("id IN (%s)" % ", ".join(["%s"] * len(ids)))
            params.extend(ids)
        if event_type is not None:
            clauses.append("type = %s")
            params.append(event_type)
        if since is not None:
            clauses.append("received_at >= %s")
            params.append(since)
        if until is not None:
            clauses.append("received_at < %s")
            params.append(until)

        sql = "SELECT id, type, raw FROM webhook_events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY received_at, id"

        # Assumes db.execute returns a DB-API style cursor.
        rows = self.db.execute(sql, tuple(params)).fetchall()

        result = ReplayResult(matched=len(rows), dry_run=dry_run)
        for event_id, etype, raw in rows:
            if dry_run:
                logger.info("dry-run: would replay %s (%s)", event_id, etype)
                continue
            try:
                handler(event_id, etype, bytes(raw))
            except Exception as exc:
                logger.exception("replay failed for %s", event_id)
                result.failed.append((event_id, exc))
                if stop_on_error:
                    break
            else:
                result.replayed += 1
        return result
