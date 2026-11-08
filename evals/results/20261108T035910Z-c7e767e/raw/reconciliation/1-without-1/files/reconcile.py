#!/usr/bin/env python3
"""Match ledger payments to Stripe payout export rows.

Pass 1: exact match on reference (+ amount and currency must agree).
Pass 2: for rows without a reference, match on amount + currency with the
        closest date within --days (one-to-one). Reported as "fuzzy".
Stripe rows of type fee/payout are not payments and are listed separately.

Usage: python3 reconcile.py [ledger.csv] [stripe_payout.csv] [--days N] [--out matches.csv]
"""
import argparse
import csv
import sys
from datetime import date

NON_PAYMENT_TYPES = {"fee", "payout"}


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["amount_minor"] = int(r["amount_minor"])  # integer minor units, no floats
        r["_date"] = date.fromisoformat(r["date"])
        r["reference"] = (r.get("reference") or "").strip()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger", nargs="?", default="src/ledger.csv")
    ap.add_argument("stripe", nargs="?", default="src/stripe_payout.csv")
    ap.add_argument("--days", type=int, default=5, help="date tolerance for fuzzy pass")
    ap.add_argument("--out", help="write match results to this CSV")
    args = ap.parse_args()

    ledger = load(args.ledger)
    stripe_all = load(args.stripe)
    stripe = [s for s in stripe_all if s.get("type") not in NON_PAYMENT_TYPES]
    skipped = [s for s in stripe_all if s.get("type") in NON_PAYMENT_TYPES]

    matches = []  # (ledger, stripe, method, note)
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
            if si in used_s:
                continue
            s = stripe[si]
            note = []
            if s["amount_minor"] != l["amount_minor"]:
                note.append(f"AMOUNT MISMATCH {l['amount_minor']} vs {s['amount_minor']}")
            if s["currency"] != l["currency"]:
                note.append(f"CURRENCY MISMATCH {l['currency']} vs {s['currency']}")
            if s["_date"] != l["_date"]:
                note.append(f"date differs by {(s['_date'] - l['_date']).days}d")
            matches.append((l, s, "reference", "; ".join(note)))
            used_s.add(si)
            used_l.add(li)
            break

    # Pass 2: amount + currency + nearest date, one-to-one
    cands = []
    for li, l in enumerate(ledger):
        if li in used_l or l["reference"]:
            continue
        for si, s in enumerate(stripe):
            if si in used_s or s["reference"]:
                continue
            if s["amount_minor"] == l["amount_minor"] and s["currency"] == l["currency"]:
                gap = abs((s["_date"] - l["_date"]).days)
                if gap <= args.days:
                    cands.append((gap, li, si))
    for gap, li, si in sorted(cands):
        if li in used_l or si in used_s:
            continue
        l, s = ledger[li], stripe[si]
        matches.append((l, s, "fuzzy", f"no reference; date differs by {gap}d - review"))
        used_l.add(li)
        used_s.add(si)

    un_l = [l for i, l in enumerate(ledger) if i not in used_l]
    un_s = [s for i, s in enumerate(stripe) if i not in used_s]

    print(f"Matched: {len(matches)}  (reference: {sum(m[2]=='reference' for m in matches)}, "
          f"fuzzy: {sum(m[2]=='fuzzy' for m in matches)})")
    for l, s, method, note in matches:
        print(f"  {l['id']:8} <-> {s['id']:8} {method:9} {l['amount_minor']:>8} {l['currency']}  {note}")
    print(f"\nLedger payments with no Stripe match: {len(un_l)}")
    for l in un_l:
        print(f"  {l['id']:8} {l['date']} {l['amount_minor']:>8} {l['currency']} ref={l['reference'] or '-'}")
    print(f"\nStripe payment rows with no ledger match: {len(un_s)}")
    for s in un_s:
        print(f"  {s['id']:8} {s['date']} {s['amount_minor']:>8} {s['currency']} ref={s['reference'] or '-'} ({s['type']})")
    print(f"\nStripe fee/payout rows (not payments): {len(skipped)}")
    for s in skipped:
        print(f"  {s['id']:8} {s['date']} {s['amount_minor']:>8} {s['currency']} ({s['type']})")

    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ledger_id", "stripe_id", "method", "amount_minor", "currency", "note"])
            for l, s, method, note in matches:
                w.writerow([l["id"], s["id"], method, l["amount_minor"], l["currency"], note])
            for l in un_l:
                w.writerow([l["id"], "", "unmatched_ledger", l["amount_minor"], l["currency"], ""])
            for s in un_s:
                w.writerow(["", s["id"], "unmatched_stripe", s["amount_minor"], s["currency"], ""])

    return 1 if (un_l or un_s or any("MISMATCH" in m[3] for m in matches)) else 0


if __name__ == "__main__":
    sys.exit(main())
