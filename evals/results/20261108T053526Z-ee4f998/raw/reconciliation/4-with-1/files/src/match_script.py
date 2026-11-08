"""Tiered, deterministic, one-to-one matcher for ledger vs Stripe payout report.

Tiers (fixed order):
  1 reference      same reference, amount, currency
  2 amount_date    same amount, currency, date within `date_window_days`
  2b amount_tol    same currency, date in window, amount within an explicit
                   tolerance. OFF unless configured; needs a written reason and
                   is recorded on every match it produces (rule 4, rule 10).
  3 payout_nets_captures_minus_fees  named grouping rule on the processor side.
"""
import csv
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Config:
    date_window_days: int = 2
    amount_tolerance_pct: float = 0.0  # 0.02 == 2%; default is exact
    tolerance_reason: str = ""         # required when tolerance > 0

    def __post_init__(self):
        if self.amount_tolerance_pct < 0:
            raise ValueError("tolerance must be >= 0")
        if self.amount_tolerance_pct and not self.tolerance_reason:
            raise ValueError("amount tolerance needs a reason (e.g. FX rounding on source X)")


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _d(row):
    return date.fromisoformat(row["date"])


def _key(row):
    return (row["date"], row["id"])


def reconcile(ours, theirs, config=Config()):
    ours = sorted(ours, key=_key)
    theirs = sorted(theirs, key=_key)
    cand = [t for t in theirs if t.get("type", "charge") == "charge"]
    used_o, used_t = set(), set()
    matches = []

    def free_t():
        return [t for t in cand if t["id"] not in used_t]

    def take(o, t, tier, **extra):
        used_o.add(o["id"])
        used_t.add(t["id"])
        matches.append({"ours": o["id"], "theirs": t["id"], "tier": tier, **extra})

    # Tier 1: reference
    for o in ours:
        if not o.get("reference"):
            continue
        for t in free_t():
            if (t.get("reference") == o["reference"] and t["amount_minor"] == o["amount_minor"]
                    and t["currency"] == o["currency"]):
                take(o, t, "reference")
                break

    # Tier 2: amount + date window, earliest first
    for o in ours:
        if o["id"] in used_o:
            continue
        for t in free_t():
            if (t["amount_minor"] == o["amount_minor"] and t["currency"] == o["currency"]
                    and abs((_d(t) - _d(o)).days) <= config.date_window_days):
                take(o, t, "amount_date")
                break

    # Tier 2b: explicit amount tolerance (off by default)
    if config.amount_tolerance_pct:
        for o in ours:
            if o["id"] in used_o:
                continue
            oa = int(o["amount_minor"])
            for t in free_t():
                ta = int(t["amount_minor"])
                if t["currency"] != o["currency"]:
                    continue
                if abs((_d(t) - _d(o)).days) > config.date_window_days:
                    continue
                if abs(ta - oa) <= abs(oa) * config.amount_tolerance_pct:
                    take(o, t, "amount_tol", tolerance_pct=config.amount_tolerance_pct,
                         tolerance_reason=config.tolerance_reason, diff_minor=ta - oa)
                    break

    # Tier 3: payout == captures + (negative) fee lines, processor side only
    groups = []
    payouts = [t for t in theirs if t.get("type") == "payout"]
    net = sum(int(t["amount_minor"]) for t in theirs if t.get("type") in ("charge", "fee"))
    for p in payouts:
        if -int(p["amount_minor"]) == net:
            groups.append({"rule": "payout_nets_captures_minus_fees", "payout": p["id"],
                           "members": [t["id"] for t in theirs if t.get("type") in ("charge", "fee")]})

    grouped = {p["payout"] for p in groups} | {m for g in groups for m in g["members"]}
    return {
        "matches": matches,
        "groups": groups,
        "unmatched_ours": [o["id"] for o in ours if o["id"] not in used_o],
        "unmatched_theirs": [t["id"] for t in theirs
                             if t["id"] not in used_t and t["id"] not in grouped],
    }
