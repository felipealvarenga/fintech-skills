#!/usr/bin/env python3
"""Match ledger payments to Stripe payout export rows.

Pass 1: exact match on reference (plus currency and amount).
Pass 2: for leftovers, match on currency + amount within a date window,
        closest date first, one-to-one.
Stripe rows of type fee/payout (non-charge) are ignored for matching.

Usage: reconcile.py [ledger.csv] [stripe_payout.csv] [--window DAYS] [--out FILE]
"""
import argparse
import csv
from datetime import date

MATCHABLE_TYPES = {"charge", "payment"}


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["amount_minor"] = int(r["amount_minor"])
        r["date"] = date.fromisoformat(r["date"])
        r["reference"] = (r.get("reference") or "").strip()
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ledger", nargs="?", default="src/ledger.csv")
    p.add_argument("stripe", nargs="?", default="src/stripe_payout.csv")
    p.add_argument("--window", type=int, default=3, help="max days apart for amount-only matches")
    p.add_argument("--out", help="write results to this CSV")
    a = p.parse_args()

    ledger = load(a.ledger)
    stripe_all = load(a.stripe)
    stripe = [s for s in stripe_all if s.get("type", "charge") in MATCHABLE_TYPES]
    ignored = [s for s in stripe_all if s not in stripe]

    matches = []  # (ledger, stripe, method)
    used_s = set()
    used_l = set()

    # Pass 1: reference
    by_ref = {}
    for i, s in enumerate(stripe):
        if s["reference"]:
            by_ref.setdefault(s["reference"], []).append(i)
    for li, l in enumerate(ledger):
        if not l["reference"]:
            continue
        for si in by_ref.get(l["reference"], []):
            s = stripe[si]
            if si not in used_s and s["currency"] == l["currency"] and s["amount_minor"] == l["amount_minor"]:
                matches.append((l, s, "reference"))
                used_s.add(si)
                used_l.add(li)
                break

    # Pass 2: amount + currency + date window, closest first
    cands = []
    for li, l in enumerate(ledger):
        if li in used_l:
            continue
        for si, s in enumerate(stripe):
            if si in used_s or s["currency"] != l["currency"] or s["amount_minor"] != l["amount_minor"]:
                continue
            # don't pair rows that carry conflicting references
            if l["reference"] and s["reference"] and l["reference"] != s["reference"]:
                continue
            gap = abs((l["date"] - s["date"]).days)
            if gap <= a.window:
                cands.append((gap, li, si))
    for gap, li, si in sorted(cands):
        if li in used_l or si in used_s:
            continue
        matches.append((ledger[li], stripe[si], f"amount+date (±{gap}d)"))
        used_l.add(li)
        used_s.add(si)

    un_l = [l for i, l in enumerate(ledger) if i not in used_l]
    un_s = [s for i, s in enumerate(stripe) if i not in used_s]

    print(f"Matched: {len(matches)}")
    for l, s, m in matches:
        print(f"  {l['id']:8} <-> {s['id']:8} {l['amount_minor']:>8} {l['currency']}  [{m}]")
    print(f"\nUnmatched ledger payments: {len(un_l)}")
    for l in un_l:
        print(f"  {l['id']:8} {l['date']} {l['amount_minor']:>8} {l['currency']} {l['reference']}")
    print(f"\nUnmatched Stripe charges: {len(un_s)}")
    for s in un_s:
        print(f"  {s['id']:8} {s['date']} {s['amount_minor']:>8} {s['currency']} {s['reference']}")
    print(f"\nIgnored Stripe rows (fees/payouts): {len(ignored)}")
    for s in ignored:
        print(f"  {s['id']:8} {s['date']} {s['amount_minor']:>8} {s['currency']} {s['type']}")

    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["status", "ledger_id", "stripe_id", "amount_minor", "currency", "method"])
            for l, s, m in matches:
                w.writerow(["matched", l["id"], s["id"], l["amount_minor"], l["currency"], m])
            for l in un_l:
                w.writerow(["unmatched_ledger", l["id"], "", l["amount_minor"], l["currency"], ""])
            for s in un_s:
                w.writerow(["unmatched_stripe", "", s["id"], s["amount_minor"], s["currency"], ""])


if __name__ == "__main__":
    main()
