"""Reference implementation for the accounting-sync vectors.

A fake accounting system with version tokens, request-id idempotency, a closed period and
change tracking; a sync that maps accounts explicitly, pushes idempotently, detects conflicts,
handles closed periods and persists rotated tokens before using them; and a drift report.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date


class Unmapped(KeyError):
    pass


class StaleToken(Exception):
    code = 5010


class PeriodClosed(Exception):
    pass


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class FakeAccounting:
    """Stands in for QuickBooks Online or Xero: ids, SyncToken-style versions, requestid dedupe,
    a book-closing date and a changes-since feed."""

    def __init__(self, closed_through: date | None = None) -> None:
        self.objects: dict[str, dict] = {}
        self.by_request: dict[str, str] = {}
        self.closed_through = closed_through
        self.changes: list[tuple[int, str]] = []
        self._tick = 0

    def _touch(self, obj_id: str) -> None:
        self._tick += 1
        self.changes.append((self._tick, obj_id))

    def create(self, payload: dict, request_id: str) -> dict:
        if request_id in self.by_request:
            return dict(self.objects[self.by_request[request_id]])
        if self.closed_through and payload["date"] <= self.closed_through:
            raise PeriodClosed(payload["date"])
        obj_id = f"je_{len(self.objects) + 1}"
        self.objects[obj_id] = {"id": obj_id, "token": 0, **payload}
        self.by_request[request_id] = obj_id
        self._touch(obj_id)
        return dict(self.objects[obj_id])

    def update(self, obj_id: str, token: int, payload: dict) -> dict:
        current = self.objects[obj_id]
        if current["token"] != token:
            raise StaleToken()
        if self.closed_through and payload["date"] <= self.closed_through:
            raise PeriodClosed(payload["date"])
        current.update(payload)
        current["token"] += 1
        self._touch(obj_id)
        return dict(current)

    def get(self, obj_id: str) -> dict:
        return dict(self.objects[obj_id])

    def edit_remotely(self, obj_id: str, **changes) -> None:
        """The accountant changes something inside the accounting system."""
        self.objects[obj_id].update(changes)
        self.objects[obj_id]["token"] += 1
        self._touch(obj_id)

    def changes_since(self, tick: int) -> list[str]:
        return [obj_id for t, obj_id in self.changes if t > tick]

    @property
    def tick(self) -> int:
        return self._tick


@dataclass
class SyncPair:
    remote_id: str
    token: int
    pushed_hash: str


@dataclass
class Sync:
    remote: FakeAccounting
    account_map: dict[str, dict[str, str]]  # tenant -> local account -> remote account id
    conflict_policy: str = "flag"  # flag | ours_wins | theirs_wins
    pairs: dict[tuple[str, str], SyncPair] = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)
    unmapped: list[dict] = field(default_factory=list)
    posted_in_open_period: list[dict] = field(default_factory=list)

    def _map(self, tenant: str, local_account: str) -> str:
        try:
            return self.account_map[tenant][local_account]
        except KeyError:
            raise Unmapped(local_account) from None

    def build_entry(self, tenant: str, day: date, lines: list[dict]) -> dict | None:
        mapped = []
        for line in lines:
            try:
                mapped.append({"account": self._map(tenant, line["account"]), "side": line["side"],
                               "amount": f"{line['amount_minor'] / 100:.2f}"})
            except Unmapped:
                self.unmapped.append({"tenant": tenant, "day": day, **line})
                return None
        return {"date": day, "lines": mapped, "memo": f"{tenant} daily summary {day}", "external_ref": f"{tenant}:{day}"}

    def push_summary(self, tenant: str, day: date, lines: list[dict], first_open_day: date | None = None) -> str:
        payload = self.build_entry(tenant, day, lines)
        if payload is None:
            return "queued_unmapped"
        key = (tenant, str(day))
        request_id = f"{tenant}-{day}"
        pair = self.pairs.get(key)
        if pair is None:
            try:
                obj = self.remote.create(payload, request_id)
            except PeriodClosed:
                if first_open_day is None:
                    raise
                payload = {**payload, "date": first_open_day, "memo": payload["memo"] + f" (original date {day}, period closed)"}
                obj = self.remote.create(payload, request_id)
                self.posted_in_open_period.append({"tenant": tenant, "day": day, "posted": first_open_day})
            self.pairs[key] = SyncPair(obj["id"], obj["token"], _hash(payload))
            return "created"
        if pair.pushed_hash == _hash(payload):
            return "unchanged"
        try:
            obj = self.remote.update(pair.remote_id, pair.token, payload)
        except StaleToken:
            current = self.remote.get(pair.remote_id)
            remote_payload = {k: current[k] for k in payload if k in current}
            if _hash(remote_payload) == pair.pushed_hash:
                obj = self.remote.update(pair.remote_id, current["token"], payload)  # only the token moved
            else:
                record = {"tenant": tenant, "day": day, "remote_id": pair.remote_id, "ours": payload, "theirs": remote_payload,
                          "policy": self.conflict_policy}
                self.conflicts.append(record)
                if self.conflict_policy == "ours_wins":
                    obj = self.remote.update(pair.remote_id, current["token"], payload)
                else:
                    pair.token = current["token"]
                    if self.conflict_policy == "theirs_wins":
                        pair.pushed_hash = _hash(remote_payload)
                    return "conflict"
        pair.token = obj["token"]
        pair.pushed_hash = _hash(payload)
        return "updated"


@dataclass
class TokenStore:
    refresh_token: str
    expires_at: str | None = None
    history: list[str] = field(default_factory=list)

    def refresh(self, token_endpoint) -> str:
        """Persist the rotated refresh token before anything else can use it."""
        response = token_endpoint(self.refresh_token)
        self.history.append(self.refresh_token)
        self.refresh_token = response["refresh_token"]
        self.expires_at = response.get("x_refresh_token_expires_at")
        return response["access_token"]


def drift_report(ours: dict[str, int], theirs: dict[str, int], threshold_minor: int = 0) -> list[dict]:
    rows = []
    for account in sorted(set(ours) | set(theirs)):
        diff = ours.get(account, 0) - theirs.get(account, 0)
        if abs(diff) > threshold_minor:
            rows.append({"account": account, "ours": ours.get(account, 0), "theirs": theirs.get(account, 0), "diff": diff})
    return rows
