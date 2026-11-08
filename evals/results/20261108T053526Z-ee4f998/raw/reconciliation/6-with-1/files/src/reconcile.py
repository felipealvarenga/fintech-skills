"""Reconcile ledger captures against a Stripe payout report.

Pure and deterministic: no clock, no I/O inside reconcile(). It never writes to the ledger.
"""
import csv
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Config:
    date_window_days: int = 2  # tier 2 window; calendar days, needs sign-off from finance


@dataclass(frozen=True)
class Line:
    source: str
    id: str
    date: date
    amount_minor: int
    currency: str
    reference: str
    type: str
    raw: dict = field(default_factory=dict, compare=False, hash=False)


@dataclass
class RunResult:
    matches: list   # dicts: tier, rule, ours (ids), theirs (ids)
    breaks: list    # dicts: side, id, reason, amount_minor, [difference_minor]


def _read(path, source):
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            yield Line(source, r["id"], date.fromisoformat(r["date"]), int(r["amount_minor"]),
                       r["currency"], r.get("reference") or "", r.get("type") or "capture", r)


def load_ledger(path):
    return list(_read(path, "ledger"))


def load_stripe(path):
    return list(_read(path, "stripe"))


def _key(l):
    return (l.date, l.id)


def reconcile(ours, theirs, config=Config()):
    ours = sorted(ours, key=_key)
    theirs = sorted(theirs, key=_key)
    matches, used_o, used_t = [], set(), set()

    def take(tier, rule, o, t):
        used_o.add(o.id)
        used_t.add(t.id)
        matches.append({"tier": tier, "rule": rule, "ours": [o.id], "theirs": [t.id]})

    charges = [t for t in theirs if t.type == "charge"]
    # Tier 1: reference + amount + currency
    for o in ours:
        if not o.reference:
            continue
        for t in charges:
            if (t.id not in used_t and t.reference == o.reference
                    and t.amount_minor == o.amount_minor and t.currency == o.currency):
                take(1, "reference", o, t)
                break
    # Tier 2: amount + currency within date window, earliest first, one-to-one
    for o in ours:
        if o.id in used_o:
            continue
        for t in charges:
            if (t.id not in used_t and t.amount_minor == o.amount_minor
                    and t.currency == o.currency
                    and abs((t.date - o.date).days) <= config.date_window_days):
                take(2, "amount_date_window", o, t)
                break

    # Tier 3 (named rule): payout_nets_fees. Matched captures + fee lines + payout == 0.
    breaks = []
    matched_charges = [t for t in charges if t.id in used_t]
    fees = [t for t in theirs if t.type == "fee"]
    fee_ids = set()
    for p in (t for t in theirs if t.type == "payout"):
        eligible = [c for c in matched_charges if c.date <= p.date and c.currency == p.currency]
        elig_fees = [f for f in fees if f.date <= p.date and f.currency == p.currency
                     and f.id not in fee_ids]
        diff = sum(c.amount_minor for c in eligible) + sum(f.amount_minor for f in elig_fees) \
            + p.amount_minor
        if diff == 0:
            fee_ids |= {f.id for f in elig_fees}
            used_t.add(p.id)
            used_t |= fee_ids
            ours_ids = [m["ours"][0] for m in matches
                        if m["theirs"][0] in {c.id for c in eligible}]
            matches.append({"tier": 3, "rule": "payout_nets_fees", "ours": sorted(ours_ids),
                            "theirs": sorted([c.id for c in eligible] + [f.id for f in elig_fees]
                                             + [p.id])})
        else:
            used_t.add(p.id)
            breaks.append({"side": "theirs", "id": p.id, "reason": "unknown",
                           "amount_minor": p.amount_minor, "difference_minor": diff})

    for o in ours:
        if o.id not in used_o:
            breaks.append({"side": "ours", "id": o.id, "reason": "missing_theirs",
                           "amount_minor": o.amount_minor})
    for t in theirs:
        if t.id not in used_t:
            breaks.append({"side": "theirs", "id": t.id,
                           "reason": "fee" if t.type == "fee" else "missing_ours",
                           "amount_minor": t.amount_minor})
    return RunResult(matches, breaks)


if __name__ == "__main__":
    import sys
    res = reconcile(load_ledger(sys.argv[1]), load_stripe(sys.argv[2]))
    for m in res.matches:
        print("MATCH", m)
    for b in res.breaks:
        print("BREAK", b)
