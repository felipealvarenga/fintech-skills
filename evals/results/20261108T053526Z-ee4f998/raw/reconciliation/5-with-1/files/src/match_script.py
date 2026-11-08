"""Matcher: ledger lines against Stripe payout lines, one-to-one, in tiers.

Tier 1: same reference, amount and currency.
Tier 2: same amount and currency, date within DATE_WINDOW_DAYS, closest date first
        (then by id, so the result is deterministic).
Tier 3: named grouping rules (see payout_net_of_fees).

A line matches at most one line on the other side. Inputs are sorted by id
before matching, so input order never changes the result.
"""
import csv
from datetime import date

# Calendar days. Parameter, not a default to trust: needs approval from finance ops.
DATE_WINDOW_DAYS = 2


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _day(line):
    return date.fromisoformat(line["date"])


def _key(line):
    return (line["amount_minor"], line["currency"])


def reconcile(ours, theirs, window_days=DATE_WINDOW_DAYS):
    ours = sorted(ours, key=lambda l: l["id"])
    theirs = sorted(theirs, key=lambda l: l["id"])
    used_o, used_t, matches = set(), set(), []

    # Tier 1: reference + amount + currency.
    for o in ours:
        if not o.get("reference"):
            continue
        for t in theirs:
            if t["id"] in used_t:
                continue
            if o["reference"] == t.get("reference") and _key(o) == _key(t):
                matches.append((o["id"], t["id"], "reference"))
                used_o.add(o["id"])
                used_t.add(t["id"])
                break

    # Tier 2: amount + currency + date window, nearest date first.
    for o in ours:
        if o["id"] in used_o:
            continue
        candidates = [
            t for t in theirs
            if t["id"] not in used_t
            and _key(o) == _key(t)
            and abs((_day(o) - _day(t)).days) <= window_days
        ]
        if candidates:
            t = min(candidates, key=lambda t: (abs((_day(o) - _day(t)).days), t["id"]))
            matches.append((o["id"], t["id"], "amount_date"))
            used_o.add(o["id"])
            used_t.add(t["id"])

    return {
        "matches": matches,
        "unmatched_ours": [o["id"] for o in ours if o["id"] not in used_o],
        "unmatched_theirs": [t["id"] for t in theirs if t["id"] not in used_t],
    }


def payout_net_of_fees(theirs):
    """Tier 3 rule: a payout equals the sum of the charges and fee lines it settles.

    Returns (payout_id, component_ids, difference_minor); difference 0 means it nets.
    Only handles a single payout and single currency; otherwise returns None.
    """
    payouts = [t for t in theirs if t.get("type") == "payout"]
    if len(payouts) != 1:
        return None
    p = payouts[0]
    parts = sorted(
        (t for t in theirs
         if t.get("type") in ("charge", "fee") and t["currency"] == p["currency"]),
        key=lambda t: t["id"],
    )
    total = sum(int(t["amount_minor"]) for t in parts)
    return p["id"], [t["id"] for t in parts], total + int(p["amount_minor"])


def match(ours, theirs):
    """Backward-compatible: list of (our_id, their_id) pairs."""
    return [(o, t) for o, t, _ in reconcile(ours, theirs)["matches"]]
