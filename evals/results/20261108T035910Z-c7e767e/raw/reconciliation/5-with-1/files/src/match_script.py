"""Matcher: tiered, deterministic, one-to-one.

Tier 1: same reference, amount and currency.
Tier 2: same amount and currency, date within DATE_WINDOW_DAYS, earliest first.
Lines matching nothing are returned as unmatched (breaks); nothing is dropped.
"""
import csv
from datetime import date

DATE_WINDOW_DAYS = 2  # parameter: needs sign-off from finance ops


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _day(line):
    return date.fromisoformat(line["date"])


def _sort(lines):
    return sorted(lines, key=lambda l: (l["date"], l["id"]))


def reconcile(ours, theirs, window_days=DATE_WINDOW_DAYS):
    """Return (matches, unmatched_ours, unmatched_theirs).

    matches: list of (our_id, their_id, tier). Each line is used at most once.
    """
    ours, theirs = _sort(ours), _sort(theirs)
    used_o, used_t = set(), set()
    matches = []

    def same_money(o, t):
        return (o["amount_minor"] == t["amount_minor"]
                and o["currency"] == t["currency"])

    # Tier 1: reference
    for o in ours:
        if not o.get("reference"):
            continue
        for t in theirs:
            if (t["id"] not in used_t and t.get("reference") == o["reference"]
                    and same_money(o, t)):
                matches.append((o["id"], t["id"], "reference"))
                used_o.add(o["id"])
                used_t.add(t["id"])
                break

    # Tier 2: amount + currency within the date window, earliest first
    for o in ours:
        if o["id"] in used_o:
            continue
        for t in theirs:
            if (t["id"] not in used_t and same_money(o, t)
                    and abs((_day(o) - _day(t)).days) <= window_days):
                matches.append((o["id"], t["id"], "amount_date"))
                used_o.add(o["id"])
                used_t.add(t["id"])
                break

    unmatched_o = [o["id"] for o in ours if o["id"] not in used_o]
    unmatched_t = [t["id"] for t in theirs if t["id"] not in used_t]
    return matches, unmatched_o, unmatched_t


def match(ours, theirs):
    """Backward-compatible: list of (our_id, their_id) pairs."""
    return [(o, t) for o, t, _ in reconcile(ours, theirs)[0]]
