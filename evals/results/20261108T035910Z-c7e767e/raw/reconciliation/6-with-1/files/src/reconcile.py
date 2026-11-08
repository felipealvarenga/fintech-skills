"""Pure reconciliation: ledger captures vs Stripe report vs bank. Never writes to the ledger."""
import csv
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Config:
    date_window_days: int = 2  # tier 2 window; needs approval by finance owner


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["amount_minor"] = int(r["amount_minor"])
        r["date"] = date.fromisoformat(r["date"])
        r["reference"] = r.get("reference") or ""
    return rows


def _key(r):
    return (r["date"], r["id"])


def _match_tiers(ours, theirs, cfg, tag):
    """Tier 1 reference+amount+currency, tier 2 amount+currency within window. One-to-one."""
    ours, theirs = sorted(ours, key=_key), sorted(theirs, key=_key)
    matches, used_o, used_t = [], set(), set()
    for tier in (1, 2):
        for o in ours:
            if o["id"] in used_o:
                continue
            for t in theirs:
                if t["id"] in used_t:
                    continue
                if o["currency"] != t["currency"] or o["amount_minor"] != t["amount_minor"]:
                    continue
                if tier == 1 and not (o["reference"] and o["reference"] == t["reference"]):
                    continue
                if tier == 2 and abs((o["date"] - t["date"]).days) > cfg.date_window_days:
                    continue
                matches.append({"rule": f"{tag}_tier{tier}", "ours": o["id"], "theirs": t["id"]})
                used_o.add(o["id"]); used_t.add(t["id"])
                break
    return (matches,
            [o for o in ours if o["id"] not in used_o],
            [t for t in theirs if t["id"] not in used_t])


def reconcile(ledger, stripe, bank, cfg=Config()):
    charges = [s for s in stripe if s["type"] == "charge"]
    fees = [s for s in stripe if s["type"] == "fee"]
    payouts = [s for s in stripe if s["type"] == "payout"]

    # Captures vs Stripe charges
    matches, open_ledger, open_charges = _match_tiers(ledger, charges, cfg, "capture")
    breaks = [{"reason": "missing_theirs", "id": o["id"]} for o in open_ledger]
    breaks += [{"reason": "missing_ours", "id": t["id"]} for t in open_charges]

    # Tier 3 rule: payout_net_of_fees = matched gross charges + fee lines (fees are negative)
    matched_charge_ids = {m["theirs"] for m in matches}
    gross = sum(c["amount_minor"] for c in charges if c["id"] in matched_charge_ids)
    fee_total = sum(f["amount_minor"] for f in fees)
    fee_lines = [{"id": f["id"], "amount_minor": f["amount_minor"], "status": "to_book"} for f in fees]
    for p in payouts:
        expected = -p["amount_minor"]
        if gross + fee_total == expected:
            matches.append({"rule": "payout_net_of_fees", "payout": p["id"],
                            "gross": gross, "fees": fee_total, "net": expected})
        else:
            breaks.append({"reason": "unknown", "id": p["id"],
                           "diff": expected - (gross + fee_total)})

    # Payout vs bank deposit: bank is positive, payout is outflow from Stripe balance
    bank_in = [{**p, "amount_minor": -p["amount_minor"]} for p in payouts]
    bm, ob, obk = _match_tiers(bank_in, bank, cfg, "bank")
    matches += bm
    breaks += [{"reason": "missing_ours", "id": b["id"]} for b in obk
               if "STRIPE" in b.get("description", "").upper()]
    breaks += [{"reason": "missing_theirs", "id": o["id"]} for o in ob]

    return {"matches": matches, "breaks": breaks, "fee_lines_to_book": fee_lines}


if __name__ == "__main__":
    import json, sys
    d = sys.argv[1] if len(sys.argv) > 1 else "src"
    print(json.dumps(reconcile(load(f"{d}/ledger.csv"), load(f"{d}/stripe_payout.csv"),
                               load(f"{d}/bank.csv")), indent=2, default=str))
