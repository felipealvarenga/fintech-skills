"""Reconcile ledger payments against a Stripe payout export.

Read-only: never touches the ledger. Writes only its own immutable run record.

Usage:
    python3 reconcile.py src/ledger.csv src/stripe_payout.csv --runs-dir runs [--window-days 2] [--as-of 2026-05-12]
"""
import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Config:
    date_window_days: int = 2  # tier 2 window, calendar days; needs finance sign-off
    unknown_page_after_days: int = 5


@dataclass(frozen=True)
class Line:
    source: str
    id: str
    date: date
    amount_minor: int
    currency: str
    reference: str
    kind: str  # stripe type; "payment" for ledger
    raw: tuple  # original row as sorted (key, value) pairs


# ---------- adapters ----------

def _norm(source, row, kind):
    return Line(source, row["id"].strip(), date.fromisoformat(row["date"].strip()),
                int(row["amount_minor"]), row["currency"].strip().upper(),
                (row.get("reference") or "").strip(), kind,
                tuple(sorted(row.items())))


def load_ledger(path):
    with open(path, newline="") as f:
        return [_norm("ledger", r, "payment") for r in csv.DictReader(f)]


def load_stripe(path):
    with open(path, newline="") as f:
        return [_norm("stripe", r, r["type"].strip().lower()) for r in csv.DictReader(f)]


# ---------- matching (pure) ----------

def reconcile(ours, theirs, config=Config(), as_of=None):
    key = lambda l: (l.date, l.id)
    ours, theirs = sorted(ours, key=key), sorted(theirs, key=key)
    as_of = as_of or max([l.date for l in ours + theirs], default=date.min)
    matches, breaks = [], []
    used_o, used_t = set(), set()

    charges = [t for t in theirs if t.kind == "charge"]

    def pair(o, t, tier):
        used_o.add(o.id); used_t.add(t.id)
        matches.append({"tier": tier, "ours": [o.id], "theirs": [t.id],
                        "amount_minor": o.amount_minor, "currency": o.currency})

    # Tier 1: reference + amount + currency
    for o in ours:
        if not o.reference:
            continue
        for t in charges:
            if (t.id not in used_t and t.reference == o.reference
                    and t.amount_minor == o.amount_minor and t.currency == o.currency):
                pair(o, t, "1_reference"); break

    # Tier 2: amount + currency, date window, earliest first; refs must not conflict
    for o in ours:
        if o.id in used_o:
            continue
        for t in charges:
            if (t.id not in used_t and t.amount_minor == o.amount_minor
                    and t.currency == o.currency
                    and abs((t.date - o.date).days) <= config.date_window_days
                    and not (o.reference and t.reference and o.reference != t.reference)):
                pair(o, t, "2_amount_date"); break

    # Tier 3 (named rule): payout == matched charges - fees, same currency, dated on/before payout.
    consumed = set()
    for p in (t for t in theirs if t.kind == "payout"):
        comp = [t for t in theirs if t.kind in ("charge", "fee") and t.id not in consumed
                and t.currency == p.currency and t.date <= p.date and
                (t.kind == "fee" or t.id in used_t)]
        if comp and sum(c.amount_minor for c in comp) == -p.amount_minor:
            consumed.update(c.id for c in comp); used_t.add(p.id)
            matches.append({"tier": "3_payout_net_of_fees", "ours": [],
                            "theirs": [p.id] + [c.id for c in comp],
                            "amount_minor": -p.amount_minor, "currency": p.currency})

    def brk(line, reason, owner):
        breaks.append({"id": line.id, "source": line.source, "reason": reason, "owner": owner,
                       "amount_minor": line.amount_minor, "currency": line.currency,
                       "date": line.date.isoformat(), "age_days": (as_of - line.date).days,
                       "pages_person": reason == "unknown"
                       and (as_of - line.date).days > config.unknown_page_after_days})

    for o in ours:
        if o.id not in used_o:
            brk(o, "missing_theirs", "payments-ops")
    for t in theirs:
        if t.id in used_t and t.kind != "fee" or t.id in consumed and t.kind == "charge":
            continue
        if t.kind == "fee":
            # Fee is explained by the payout but has no ledger line: book it (human posts entry).
            brk(t, "fee", "finance")
        elif t.kind == "charge":
            brk(t, "missing_ours", "payments-ops")
        else:
            brk(t, "unknown", "finance")

    matched_amt = sum(m["amount_minor"] for m in matches if m["tier"] != "3_payout_net_of_fees")
    total_amt = sum(abs(l.amount_minor) for l in ours)
    metrics = {
        "match_rate_count": len({i for m in matches for i in m["ours"]}) / len(ours) if ours else 1.0,
        "match_rate_amount": matched_amt / total_amt if total_amt else 1.0,
        "breaks_by_reason": {r: sum(b["reason"] == r for b in breaks) for r in sorted({b["reason"] for b in breaks})},
        "oldest_break_age_days": max((b["age_days"] for b in breaks), default=0),
        "unknown_amount_minor": sum(abs(b["amount_minor"]) for b in breaks if b["reason"] == "unknown"),
    }
    return {"matches": matches, "breaks": breaks, "metrics": metrics}


# ---------- run record ----------

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger"); ap.add_argument("stripe")
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--window-days", type=int, default=Config.date_window_days)
    ap.add_argument("--as-of", type=date.fromisoformat, default=None)
    a = ap.parse_args(argv)
    cfg = Config(date_window_days=a.window_days)
    result = reconcile(load_ledger(a.ledger), load_stripe(a.stripe), cfg, a.as_of)
    now = datetime.now(timezone.utc)
    record = {"run_at": now.isoformat(), "params": asdict(cfg),
              "inputs": {a.ledger: _sha(a.ledger), a.stripe: _sha(a.stripe)}, **result}
    out = Path(a.runs_dir); out.mkdir(parents=True, exist_ok=True)
    path = out / f"run_{now:%Y%m%dT%H%M%S%fZ}.json"
    with open(path, "x") as f:  # "x": never overwrite a prior run
        json.dump(record, f, indent=2)
    print(json.dumps(result["metrics"], indent=2))
    for b in result["breaks"]:
        print(f"BREAK {b['reason']:<15} {b['source']}:{b['id']} {b['amount_minor']} {b['currency']} owner={b['owner']}")
    print(f"run record: {path}")
    return 1 if any(b["pages_person"] for b in result["breaks"]) else 0


if __name__ == "__main__":
    sys.exit(main())
