"""Tiered, one-to-one matcher.

Tier 1: same reference, currency and exact amount.
Tier 2: same currency, date within `window_days`, amount equal or within
        `amount_tolerance_pct` (default 0). Closest amount, then earliest date wins.

The tolerance is a parameter, never a default, and is recorded on every match.
"""
import csv
from datetime import date

# Approved tolerance for the Stripe payout source (reason must be stated).
STRIPE_TOLERANCE_PCT = 2.0
STRIPE_TOLERANCE_REASON = "requested 2% amount tolerance for stripe_payout; review breaks it hides"


def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def _amt(r):
    return int(r["amount_minor"])


def _day(r):
    return date.fromisoformat(r["date"])


def _within(a, b, pct):
    # integer math: |a-b| * 100 <= pct * |a|  (pct in percent, scaled by 1000)
    return abs(a - b) * 100_000 <= int(round(pct * 1000)) * abs(a)


def match(ours, theirs, amount_tolerance_pct=0.0, tolerance_reason=None,
          window_days=2):
    """Return (matches, unmatched_ours, unmatched_theirs). Deterministic, pure."""
    if amount_tolerance_pct and not tolerance_reason:
        raise ValueError("amount tolerance requires a stated reason")
    ours = sorted(ours, key=lambda r: (r["date"], r["id"]))
    theirs = sorted(
        (t for t in theirs if t.get("type", "charge") == "charge"),
        key=lambda r: (r["date"], r["id"]),
    )
    used_t, used_o, matches = set(), set(), []

    def record(o, t, tier, tol):
        used_o.add(o["id"])
        used_t.add(t["id"])
        matches.append({
            "ours": o["id"], "theirs": t["id"], "tier": tier,
            "amount_diff_minor": _amt(t) - _amt(o),
            "tolerance_pct": tol,
            "tolerance_reason": tolerance_reason if tol else None,
        })

    # Tier 1: reference
    for o in ours:
        if not o["reference"]:
            continue
        for t in theirs:
            if (t["id"] not in used_t and t["reference"] == o["reference"]
                    and t["currency"] == o["currency"]
                    and _amt(t) == _amt(o)):
                record(o, t, "reference", 0.0)
                break

    # Tier 2: amount (+ optional tolerance) and date window
    for o in ours:
        if o["id"] in used_o:
            continue
        cands = [
            t for t in theirs
            if t["id"] not in used_t and t["currency"] == o["currency"]
            and abs((_day(t) - _day(o)).days) <= window_days
            and _within(_amt(o), _amt(t), amount_tolerance_pct)
        ]
        if cands:
            t = min(cands, key=lambda t: (abs(_amt(t) - _amt(o)), t["date"], t["id"]))
            record(o, t, "amount_date",
                   amount_tolerance_pct if _amt(t) != _amt(o) else 0.0)

    return (
        matches,
        [o for o in ours if o["id"] not in used_o],
        [t for t in theirs if t["id"] not in used_t],
    )


if __name__ == "__main__":
    ours = load("src/ledger.csv")
    theirs = load("src/stripe_payout.csv")
    m, uo, ut = match(ours, theirs, STRIPE_TOLERANCE_PCT, STRIPE_TOLERANCE_REASON)
    print(f"matched={len(m)} unmatched_ours={len(uo)} unmatched_theirs={len(ut)} "
          f"rate={len(m) / len(ours):.0%}")
