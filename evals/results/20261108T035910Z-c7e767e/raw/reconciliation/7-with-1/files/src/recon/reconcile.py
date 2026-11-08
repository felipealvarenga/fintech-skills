"""Pure, deterministic reconciliation. No I/O, no clock, no ledger writes."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .metrics import compute_metrics
from .models import OWNERS, Break, Config, Line, Match, RunResult


def business_days_between(a: date, b: date) -> int:
    """Weekdays between two dates (order-insensitive)."""
    if a > b:
        a, b = b, a
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _key(l: Line):
    return (l.date, l.id)


def reconcile(ours: list[Line], theirs: list[Line], config: Config) -> RunResult:
    ours = sorted(ours, key=_key)
    theirs = sorted(theirs, key=_key)
    o_open = {l.id: l for l in ours}
    t_open = {l.id: l for l in theirs}
    matches: list[Match] = []

    def take(o_ids, t_ids, tier, rule, line):
        for i in o_ids:
            del o_open[i]
        for i in t_ids:
            del t_open[i]
        matches.append(Match(tier, rule, tuple(o_ids), tuple(t_ids), line.amount_minor, line.currency))

    # Tier 1: reference + amount + currency
    for o in ours:
        if o.id not in o_open or not o.reference:
            continue
        for t in theirs:
            if (t.id in t_open and t.reference == o.reference
                    and t.amount_minor == o.amount_minor and t.currency == o.currency):
                take([o.id], [t.id], 1, "reference", o)
                break

    # Tier 2: amount + currency, date within window, earliest first
    for o in ours:
        if o.id not in o_open:
            continue
        for t in theirs:
            if (t.id in t_open and t.amount_minor == o.amount_minor and t.currency == o.currency
                    and business_days_between(o.date, t.date) <= config.date_window_days):
                take([o.id], [t.id], 2, "amount_date_window", o)
                break

    # Tier 3 (named rule): one payout = sum of our captures and fee lines sharing its reference
    if config.enable_payout_rule:
        for t in theirs:
            if t.id not in t_open or not t.reference:
                continue
            group = [o for o in ours if o.id in o_open and o.reference == t.reference
                     and o.currency == t.currency]
            if len(group) >= 2 and sum(o.amount_minor for o in group) == t.amount_minor:
                take([o.id for o in group], [t.id], 3, "payout_equals_captures_minus_fees", t)

    breaks = _classify(list(o_open.values()), list(t_open.values()), ours, theirs, matches, config)
    metrics = compute_metrics(ours, theirs, matches, breaks)
    alerts = _alerts(breaks, metrics, config)
    return RunResult(tuple(matches), tuple(breaks), metrics, tuple(alerts))


def _classify(o_rest, t_rest, ours, theirs, matches, config) -> list[Break]:
    matched_sig = {
        "ours": {(l.reference, l.amount_minor, l.currency) for l in ours
                 if any(l.id in m.ours for m in matches) and l.reference},
        "theirs": {(l.reference, l.amount_minor, l.currency) for l in theirs
                   if any(l.id in m.theirs for m in matches) and l.reference},
    }
    refs = {"ours": defaultdict(set), "theirs": defaultdict(set)}
    for l in o_rest:
        if l.reference:
            refs["ours"][l.reference].add(l.currency)
    for l in t_rest:
        if l.reference:
            refs["theirs"][l.reference].add(l.currency)

    out = []
    for side, rest in (("ours", o_rest), ("theirs", t_rest)):
        other = "theirs" if side == "ours" else "ours"
        for l in rest:
            age = (config.as_of - l.date).days
            sig = (l.reference, l.amount_minor, l.currency)
            if l.reference and sig in matched_sig[side]:
                reason, note = "duplicate", "same reference/amount already matched"
            elif l.reference and refs[other].get(l.reference) and l.currency not in refs[other][l.reference]:
                reason, note = "fx", "same reference, different currency; needs rate line"
            elif side == "theirs" and l.raw.get("type") == "fee":
                reason, note = "fee", "processor fee not yet booked"
            elif side == "ours" and business_days_between(l.date, config.as_of) <= config.date_window_days:
                reason, note = "timing", "within clearing window"
            elif side == "ours":
                reason, note = "missing_theirs", "not in counterparty report"
            elif l.raw.get("type") in ("payout", "capture", "charge"):
                reason, note = "missing_ours", "not in our records"
            else:
                reason, note = "unknown", "no rule explains this line"
            out.append(Break(side, l.id, reason, OWNERS[reason], age, l.amount_minor, l.currency, note))
    return sorted(out, key=lambda b: (b.side, b.line_id))


def _alerts(breaks, metrics, c: Config) -> list[str]:
    a = []
    for b in breaks:
        if b.reason == "unknown" and b.age_days > c.unknown_page_after_days:
            a.append(f"PAGE {b.owner}: unknown break {b.side}/{b.line_id} aged {b.age_days}d")
    if metrics["match_rate_count"] < c.min_match_rate_count:
        a.append("match rate by count below threshold")
    if metrics["match_rate_amount"] < c.min_match_rate_amount:
        a.append("match rate by amount below threshold")
    if metrics["oldest_break_days"] > c.max_oldest_break_days:
        a.append("oldest open break exceeds threshold")
    if metrics["unknown_amount_minor"] > c.max_unknown_minor:
        a.append("amount in unknown exceeds threshold")
    return a
