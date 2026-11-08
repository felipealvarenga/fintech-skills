"""Reference implementation for the audit-trail vectors.

An append-only, hash-chained audit log with per-object sequences, required reason codes for
human actors, dual identity for agents, masking of sensitive fields and same-transaction
semantics for mutations.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

ACTOR_TYPES = {"user", "support", "service", "agent", "system"}
HUMAN = {"user", "support"}


class AuditError(ValueError):
    pass


def _mask(value) -> str:
    s = str(value)
    return "*" * max(0, len(s) - 2) + s[-2:]


@dataclass(frozen=True)
class Event:
    event_id: str
    object_type: str
    object_id: str
    sequence: int
    action: str
    actor_type: str
    actor_id: str
    on_behalf_of: str | None
    before: dict | None
    after: dict | None
    reason_code: str | None
    reason_text: str | None
    request_id: str
    occurred_at: str
    recorded_at: str
    prev_hash: str
    hash: str


@dataclass
class AuditLog:
    clock: object = staticmethod(lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    masked_fields: set[str] = field(default_factory=lambda: {"cpf", "cnpj", "document", "account_number", "email"})
    _events: list[Event] = field(default_factory=list)
    _seq: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def _masked(self, values: dict | None) -> dict | None:
        if values is None:
            return None
        return {k: (_mask(v) if k in self.masked_fields else v) for k, v in values.items()}

    def append(self, *, object_type: str, object_id: str, action: str, actor_type: str, actor_id: str,
               request_id: str, before: dict | None = None, after: dict | None = None,
               reason_code: str | None = None, reason_text: str | None = None,
               on_behalf_of: str | None = None, occurred_at: datetime | None = None) -> Event:
        if actor_type not in ACTOR_TYPES:
            raise AuditError(f"unknown actor type {actor_type!r}")
        if actor_type in HUMAN and not reason_code:
            raise AuditError("human actions need a reason code")
        if actor_type == "agent" and not on_behalf_of:
            raise AuditError("agent actions name who they act for")
        if not request_id:
            raise AuditError("request id is required")
        key = (object_type, object_id)
        seq = self._seq.get(key, 0) + 1
        prev = self._events[-1].hash if self._events else "0" * 64
        now = self.clock()
        body = {
            "object_type": object_type, "object_id": object_id, "sequence": seq, "action": action,
            "actor_type": actor_type, "actor_id": actor_id, "on_behalf_of": on_behalf_of,
            "before": self._masked(before), "after": self._masked(after),
            "reason_code": reason_code, "reason_text": reason_text, "request_id": request_id,
            "occurred_at": (occurred_at or now).isoformat(), "recorded_at": now.isoformat(), "prev_hash": prev,
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        event = Event(event_id=f"evt_{len(self._events) + 1}", hash=digest, **body)
        self._events.append(event)
        self._seq[key] = seq
        return event

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for e in self._events:
            body = {k: getattr(e, k) for k in Event.__dataclass_fields__ if k not in ("event_id", "hash")}
            if e.prev_hash != prev or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != e.hash:
                return False
            prev = e.hash
        return True

    def query(self, *, object_type: str | None = None, object_id: str | None = None,
              actor_id: str | None = None, since: str | None = None, until: str | None = None) -> list[Event]:
        out = []
        for e in self._events:
            if object_type and e.object_type != object_type:
                continue
            if object_id and e.object_id != object_id:
                continue
            if actor_id and e.actor_id != actor_id:
                continue
            if since and e.occurred_at < since:
                continue
            if until and e.occurred_at > until:
                continue
            out.append(e)
        return out

    def export(self, events: list[Event]) -> list[dict]:
        return [{"schema": "audit-export/1", **{k: getattr(e, k) for k in Event.__dataclass_fields__}} for e in events]


def mutate(state: dict, object_type: str, object_id: str, change: dict, log: AuditLog, **audit) -> dict:
    """Apply a change and its audit event as one unit: no event, no change."""
    before = dict(state.get(object_id, {}))
    after = {**before, **change}
    log.append(object_type=object_type, object_id=object_id, before=before, after=after, **audit)
    state[object_id] = after
    return after
