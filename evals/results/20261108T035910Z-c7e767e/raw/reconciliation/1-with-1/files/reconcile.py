#!/usr/bin/env python3
"""Reconcile the ledger (src/ledger.csv) against the Stripe payout export.

Usage: python3 reconcile.py [--ledger P] [--stripe P] [--runs-dir DIR]
                            [--window-days N] [--as-of YYYY-MM-DD]

Read-only on both inputs. The only thing written is an immutable run record.

Tiers (fixed order, deterministic, one-to-one):
  1  reference + amount + currency
  2  amount + currency, date within window_days, earliest first
     (skipped if both sides carry references and they differ)
  3  named rule `payout_nets_charges_and_fees`: a Stripe payout must equal
     all not-yet-paid-out charges plus fee lines up to the payout date.
"""
import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Config:
    window_days: int = 2          # tier 2 date window (calendar days); needs sign-off
    as_of: str = ""               # YYYY-MM-DD, used for break age
    unknown_page_after_days: int = 2


# ---------- adapters: one per source, same line shape ----------

def _line(source, id_, d, amount, cur, ref, desc, raw):
    return {"source": source, "id": id_, "date": d, "amount_minor": int(amount),
            "currency": cur.strip().upper(), "reference": (ref or "").strip(),
            "description": desc, "raw": raw}


def load_ledger(path):
    with open(path, newline="") as f:
        return [_line("ledger", r["id"], r["date"], r["amount_minor"], r["currency"],
                      r["reference"], "payment", r) for r in csv.DictReader(f)]


def load_stripe(path):
    with open(path, newline="") as f:
        return [_line("stripe", r["id"], r["date"], r["amount_minor"], r["currency"],
                      r["reference"], r["type"], r) for r in csv.DictReader(f)]


# ---------- matching ----------

def _key(l):
    return (l["date"], l["id"])


def _days(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def reconcile(ours, theirs, config):
    """Pure: no I/O, no clock. Returns matches, breaks, metrics."""
    ours = sorted(ours, key=_key)
    theirs = sorted(theirs, key=_key)
    charges = [t for t in theirs if t["description"] == "charge"]
    fees = [t for t in theirs if t["description"] == "fee"]
    payouts = [t for t in theirs if t["description"] == "payout"]
    other = [t for t in theirs if t["description"] not in ("charge", "fee", "payout")]

    used_o, used_t = set(), set()
    matches = []

    def pair(tier, o, t):
        used_o.add(o["id"]); used_t.add(t["id"])
        matches.append({"tier": tier, "ours": o["id"], "theirs": t["id"],
                        "amount_minor": o["amount_minor"], "currency": o["currency"]})

    # Tier 1: reference
    for o in ours:
        if not o["reference"]:
            continue
        for t in charges:
            if (t["id"] not in used_t and t["reference"] == o["reference"]
                    and t["amount_minor"] == o["amount_minor"]
                    and t["currency"] == o["currency"]):
                pair(1, o, t)
                break

    # Tier 2: amount + currency + date window
    for o in ours:
        if o["id"] in used_o:
            continue
        for t in charges:  # sorted: earliest first
            if t["id"] in used_t:
                continue
            if (t["amount_minor"] == o["amount_minor"] and t["currency"] == o["currency"]
                    and _days(o["date"], t["date"]) <= config.window_days
                    and not (o["reference"] and t["reference"] and o["reference"] != t["reference"])):
                pair(2, o, t)
                break

    # Tier 3: payout_nets_charges_and_fees (Stripe-side check of the payout)
    groups, used_p, in_group = [], set(), set()
    for p in payouts:
        members = [x for x in charges + fees
                   if x["id"] not in in_group and x["currency"] == p["currency"]
                   and x["date"] <= p["date"]]
        if sum(x["amount_minor"] for x in members) == -p["amount_minor"]:
            used_p.add(p["id"])
            in_group.update(x["id"] for x in members)
            groups.append({"tier": 3, "rule": "payout_nets_charges_and_fees",
                           "payout": p["id"], "members": [x["id"] for x in members],
                           "amount_minor": -p["amount_minor"], "currency": p["currency"]})

    # Breaks
    breaks = []

    def brk(reason, owner, l, note):
        breaks.append({"reason": reason, "owner": owner, "source": l["source"], "id": l["id"],
                       "date": l["date"], "amount_minor": l["amount_minor"],
                       "currency": l["currency"], "note": note,
                       "age_days": (_days(config.as_of, l["date"]) if config.as_of else None)})

    for o in ours:
        if o["id"] not in used_o:
            brk("missing_theirs", "payments-ops", o, "ledger payment not found in Stripe export")
    for t in charges:
        if t["id"] not in used_t:
            brk("missing_ours", "finance", t, "Stripe charge not in ledger")
    for f in fees:  # known deduction, not in ledger: book it, do not hide it
        brk("fee", "accounting", f, "Stripe fee not booked in ledger")
    for p in payouts:
        if p["id"] not in used_p:
            brk("unknown", "finance", p, "payout does not equal charges plus fees to date")
    for x in other:
        brk("unknown", "finance", x, "unrecognised Stripe line type")
    for b in breaks:
        b["pages_person"] = (b["reason"] == "unknown" and b["age_days"] is not None
                             and b["age_days"] > config.unknown_page_after_days)

    # Metrics
    n_o = len(ours)
    amt_o = sum(o["amount_minor"] for o in ours)
    m_amt = sum(o["amount_minor"] for o in ours if o["id"] in used_o)
    by_reason = {}
    for b in breaks:
        by_reason[b["reason"]] = by_reason.get(b["reason"], 0) + 1
    ages = [b["age_days"] for b in breaks if b["age_days"] is not None]
    metrics = {
        "match_rate_count": len(used_o) / n_o if n_o else 1.0,
        "match_rate_amount": m_amt / amt_o if amt_o else 1.0,
        "breaks_by_reason": by_reason,
        "oldest_break_age_days": max(ages) if ages else None,
        "unknown_amount_minor": sum(b["amount_minor"] for b in breaks if b["reason"] == "unknown"),
    }
    return {"matches": matches, "groups": groups, "breaks": breaks, "metrics": metrics}


# ---------- CLI + immutable run record ----------

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(here / "src/ledger.csv"))
    ap.add_argument("--stripe", default=str(here / "src/stripe_payout.csv"))
    ap.add_argument("--runs-dir", default=str(here / "runs"))
    ap.add_argument("--window-days", type=int, default=2)
    ap.add_argument("--as-of", default=date.today().isoformat())
    a = ap.parse_args(argv)

    cfg = Config(window_days=a.window_days, as_of=a.as_of)
    result = reconcile(load_ledger(a.ledger), load_stripe(a.stripe), cfg)
    now = datetime.now(timezone.utc)
    record = {"run_at": now.isoformat(),
              "inputs": {"ledger": {"path": a.ledger, "sha256": _sha(a.ledger)},
                         "stripe": {"path": a.stripe, "sha256": _sha(a.stripe)}},
              "config": cfg.__dict__, **result}
    runs = Path(a.runs_dir)
    runs.mkdir(parents=True, exist_ok=True)
    out = runs / f"run_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    with open(out, "x") as f:  # "x": never overwrite a previous run
        json.dump(record, f, indent=2)

    for m in result["matches"]:
        print(f"MATCH  tier{m['tier']}  {m['ours']} <-> {m['theirs']}  {m['amount_minor']} {m['currency']}")
    for g in result["groups"]:
        print(f"GROUP  tier3 {g['rule']}  payout {g['payout']} = {', '.join(g['members'])}")
    for b in result["breaks"]:
        print(f"BREAK  {b['reason']:<14} {b['source']}:{b['id']}  {b['amount_minor']} {b['currency']}"
              f"  owner={b['owner']}  {b['note']}" + ("  [PAGE]" if b["pages_person"] else ""))
    print("METRICS", json.dumps(result["metrics"]))
    print("RUN RECORD", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
