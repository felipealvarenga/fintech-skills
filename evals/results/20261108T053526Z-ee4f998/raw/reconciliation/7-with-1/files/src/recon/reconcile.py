"""Pure, deterministic reconciliation. No I/O, no clock, no database.

Tiers run in a fixed order; a line matches at most once.
  1. reference + amount + currency
  2. amount + currency within a business-day window, earliest first
  3. named grouping rules (payout = captures - fees)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Iterable

from .metrics import compute_metrics
from .models import Break, Config, Line, Match, RunResult


def business_days_between(a: date, b: date) -> int:
    """Weekdays between two dates (order-independent). Holidays are not modelled."""
    if a > b:
        a, b = b, a
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _sort(lines: Iterable[Line]) -> list[Line]:
    return sorted(lines, key=lambda l: (l.date, l.id, l.amount_minor, l.currency, l.reference))


def _tier1(ours: list[Line], theirs: list[Line], used_o: set, used_t: set) -> list[Match]:
    out: list[Match] = []
    for t in theirs:
        if t.kind != "payment" or not t.reference or t.id in used_t:
            continue
        for o in ours:
            if (o.kind == "payment" and o.id not in used_o and o.reference == t.reference
                    and o.amount_minor == t.amount_minor and o.currency == t.currency):
                used_o.add(o.id); used_t.add(t.id)
                out.append(Match("tier1_reference", (o.id,), (t.id,), t.amount_minor, t.currency))
                break
    return out


def _tier2(ours: list[Line], theirs: list[Line], used_o: set, used_t: set, window: int) -> list[Match]:
    out: list[Match] = []
    for t in theirs:
        if t.kind != "payment" or t.id in used_t:
            continue
        cands = [o for o in ours
                 if o.kind == "payment" and o.id not in used_o
                 and o.amount_minor == t.amount_minor and o.currency == t.currency
                 and business_days_between(o.date, t.date) <= window]
        if not cands:
            continue
        # earliest first; ties broken by id (inputs are already sorted, so this is stable)
        o = min(cands, key=lambda c: (c.date, c.id))
        used_o.add(o.id); used_t.add(t.id)
        out.append(Match("tier2_date_window", (o.id,), (t.id,), t.amount_minor, t.currency))
    return out


def payout_gross_minus_fees(ours: list[Line], theirs: list[Line], used_o: set, used_t: set) -> list[Match]:
    """Named tier 3 rule: a processor payout equals the ledger captures in its
    group minus the processor's fee lines in the same group (rule 10)."""
    out: list[Match] = []
    for p in theirs:
        if p.kind != "payout" or not p.group or p.id in used_t:
            continue
        caps = [o for o in ours if o.kind == "payment" and o.id not in used_o
                and o.group == p.group and o.currency == p.currency]
        fees = [t for t in theirs if t.kind == "fee" and t.id not in used_t
                and t.group == p.group and t.currency == p.currency]
        if not caps:
            continue
        if sum(c.amount_minor for c in caps) - sum(f.amount_minor for f in fees) != p.amount_minor:
            continue
        for c in caps:
            used_o.add(c.id)
        for f in fees:
            used_t.add(f.id)
        used_t.add(p.id)
        out.append(Match("tier3:payout_gross_minus_fees",
                         tuple(c.id for c in caps),
                         tuple([p.id] + [f.id for f in fees]),
                         p.amount_minor, p.currency))
    return out


TIER3_RULES: tuple[Callable, ...] = (payout_gross_minus_fees,)


def _classify(line: Line, side: str, other_unmatched: list[Line], matched_keys: set,
              cfg: Config) -> tuple[str, str]:
    if line.kind == "fee":
        return "fee", "fee line with no matching payout; book the fee"
    key = (side, line.reference, line.amount_minor, line.currency)
    if line.reference and key in matched_keys:
        return "duplicate", "same reference and amount already matched on this side"
    if line.reference:
        for x in other_unmatched:
            if x.reference == line.reference:
                if x.currency != line.currency:
                    return "fx", f"same reference, currency {line.currency} vs {x.currency}"
                if x.amount_minor != line.amount_minor:
                    return "unknown", (f"same reference, amount {line.amount_minor} "
                                       f"vs {x.amount_minor}")
    age = (cfg.as_of - line.date).days
    if business_days_between(line.date, cfg.as_of) <= cfg.window_business_days:
        return "timing", f"age {age}d within window; expected to clear"
    return ("missing_theirs" if side == "ours" else "missing_ours"), "outside window, no counterpart"


def reconcile(ours: Iterable[Line], theirs: Iterable[Line], cfg: Config) -> RunResult:
    o_sorted, t_sorted = _sort(ours), _sort(theirs)
    used_o: set[str] = set()
    used_t: set[str] = set()

    matches: list[Match] = []
    matches += _tier1(o_sorted, t_sorted, used_o, used_t)
    matches += _tier2(o_sorted, t_sorted, used_o, used_t, cfg.window_business_days)
    for rule in TIER3_RULES:
        matches += rule(o_sorted, t_sorted, used_o, used_t)

    matched_keys = {("ours", l.reference, l.amount_minor, l.currency) for l in o_sorted if l.id in used_o}
    matched_keys |= {("theirs", l.reference, l.amount_minor, l.currency) for l in t_sorted if l.id in used_t}
    left_o = [l for l in o_sorted if l.id not in used_o]
    left_t = [l for l in t_sorted if l.id not in used_t]

    breaks: list[Break] = []
    for side, lines, other in (("ours", left_o, left_t), ("theirs", left_t, left_o)):
        for l in lines:
            reason, detail = _classify(l, side, other, matched_keys, cfg)
            breaks.append(Break(side, l.id, reason, cfg.owners[reason],
                                (cfg.as_of - l.date).days, l.amount_minor, l.currency, detail))

    all_lines = o_sorted + t_sorted
    metrics, alerts = compute_metrics(all_lines, matches, breaks, cfg)
    return RunResult(tuple(matches), tuple(breaks), metrics, tuple(alerts))
