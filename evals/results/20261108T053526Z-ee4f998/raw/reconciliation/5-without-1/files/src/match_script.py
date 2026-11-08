"""Matcher: pairs ledger lines to payout lines.

Each payout line is used at most once. Lines are paired by reference first
(when both sides have one), then by amount + currency, preferring the
closest date, so equal-amount payments no longer collapse onto one line.
"""
import csv
from datetime import date


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _same_amount(o, t):
    return (o["amount_minor"] == t["amount_minor"]
            and o.get("currency") == t.get("currency"))


def _days_apart(o, t):
    try:
        return abs((date.fromisoformat(o["date"]) - date.fromisoformat(t["date"])).days)
    except (KeyError, ValueError):
        return 10**9


def match(ours, theirs):
    matched = []
    used = set()  # indexes into theirs
    pending = []

    # Pass 1: exact reference match (same amount required).
    for o in ours:
        ref = o.get("reference")
        hit = None
        if ref:
            for i, t in enumerate(theirs):
                if i not in used and t.get("reference") == ref and _same_amount(o, t):
                    hit = i
                    break
        if hit is None:
            pending.append(o)
        else:
            used.add(hit)
            matched.append((o["id"], theirs[hit]["id"]))

    # Pass 2: amount + currency, closest date, each payout line used once.
    for o in pending:
        candidates = [(_days_apart(o, t), i) for i, t in enumerate(theirs)
                      if i not in used and _same_amount(o, t)]
        if candidates:
            _, i = min(candidates)
            used.add(i)
            matched.append((o["id"], theirs[i]["id"]))

    return matched
