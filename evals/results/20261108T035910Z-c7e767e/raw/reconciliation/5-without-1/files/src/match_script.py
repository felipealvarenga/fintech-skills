"""Matcher: pairs lines one-to-one.

Pass 1: exact match on a non-empty reference (plus amount and currency).
Pass 2: for the remainder, match on amount and currency, choosing the
closest date. Each line on either side is used at most once.
"""
import csv
from datetime import date


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _days_apart(a, b):
    return abs((date.fromisoformat(a["date"]) - date.fromisoformat(b["date"])).days)


def _same_money(o, t):
    return (o["amount_minor"] == t["amount_minor"]
            and o.get("currency") == t.get("currency"))


def match(ours, theirs):
    matched = []
    used_ours = set()
    used_theirs = set()

    # Pass 1: reference matches are unambiguous.
    by_ref = {}
    for j, t in enumerate(theirs):
        ref = (t.get("reference") or "").strip()
        if ref:
            by_ref.setdefault(ref, []).append(j)
    for i, o in enumerate(ours):
        ref = (o.get("reference") or "").strip()
        for j in by_ref.get(ref, []) if ref else []:
            if j not in used_theirs and _same_money(o, theirs[j]):
                matched.append((o["id"], theirs[j]["id"]))
                used_ours.add(i)
                used_theirs.add(j)
                break

    # Pass 2: amount + currency, closest date wins; ties go to file order.
    for i, o in enumerate(ours):
        if i in used_ours:
            continue
        best = None
        for j, t in enumerate(theirs):
            if j in used_theirs or not _same_money(o, t):
                continue
            d = _days_apart(o, t)
            if best is None or d < best[0]:
                best = (d, j)
        if best:
            matched.append((o["id"], theirs[best[1]]["id"]))
            used_ours.add(i)
            used_theirs.add(best[1])

    return matched
