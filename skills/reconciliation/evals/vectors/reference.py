"""Reference matcher for the reconciliation vectors.

Pure and deterministic: tier 1 matches reference, amount and currency; tier 2 matches amount
and currency within a date window, earliest first. One-to-one. Never writes anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Line:
    id: str
    date: date
    amount: int
    currency: str
    reference: str | None = None
    description: str = ""


@dataclass(frozen=True)
class Match:
    ours_id: str
    theirs_id: str
    tier: str


@dataclass
class RunResult:
    matches: list[Match] = field(default_factory=list)
    unmatched_ours: list[str] = field(default_factory=list)
    unmatched_theirs: list[str] = field(default_factory=list)


def _key(line: Line) -> tuple:
    return (line.date, line.amount, line.currency, line.reference or "", line.id)


def reconcile(ours: list[Line], theirs: list[Line], date_window_days: int = 2) -> RunResult:
    ours_sorted = sorted(ours, key=_key)
    theirs_sorted = sorted(theirs, key=_key)
    used_theirs: set[str] = set()
    result = RunResult()
    remaining_ours: list[Line] = []

    # Tier 1: reference + amount + currency
    by_ref: dict[tuple, list[Line]] = {}
    for t in theirs_sorted:
        if t.reference:
            by_ref.setdefault((t.reference, t.amount, t.currency), []).append(t)
    for o in ours_sorted:
        candidates = by_ref.get((o.reference, o.amount, o.currency), []) if o.reference else []
        candidate = next((c for c in candidates if c.id not in used_theirs), None)
        if candidate is None:
            remaining_ours.append(o)
            continue
        used_theirs.add(candidate.id)
        result.matches.append(Match(o.id, candidate.id, "reference"))

    # Tier 2: amount + currency within the date window, earliest first
    by_amount: dict[tuple, list[Line]] = {}
    for t in theirs_sorted:
        if t.id not in used_theirs:
            by_amount.setdefault((t.amount, t.currency), []).append(t)
    for o in remaining_ours:
        candidate = None
        for c in by_amount.get((o.amount, o.currency), []):
            if c.id in used_theirs:
                continue
            if abs((c.date - o.date).days) <= date_window_days:
                candidate = c
                break
        if candidate is None:
            result.unmatched_ours.append(o.id)
            continue
        used_theirs.add(candidate.id)
        result.matches.append(Match(o.id, candidate.id, "amount_date"))

    result.unmatched_theirs = [t.id for t in theirs_sorted if t.id not in used_theirs]
    result.matches.sort(key=lambda mt: (mt.ours_id, mt.theirs_id))
    result.unmatched_ours.sort()
    result.unmatched_theirs.sort()
    return result
