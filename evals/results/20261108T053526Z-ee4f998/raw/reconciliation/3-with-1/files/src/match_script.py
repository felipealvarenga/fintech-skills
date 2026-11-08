"""Tiered, deterministic, one-to-one matcher with breaks and proposed adjustments.

The job never writes to the ledger. Remaining differences become breaks; each
break gets a *proposed* adjustment that a person (or a separately approved
rule) posts, referencing the break id.
"""
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Config:
    window_days: int = 2  # explicit date window for tier 2 (calendar days); needs approval
    owner: str = "finance-ops"


@dataclass
class RunResult:
    matches: list  # dicts: ours, theirs, tier, rule
    breaks: list  # dicts: id, side, line_id, amount_minor, currency, reason, owner
    proposed_adjustments: list  # dicts, status always "proposed"
    metrics: dict


def load(path):
    with open(path, newline="") as f:
        return [normalize(r) for r in csv.DictReader(f)]


def normalize(r):
    return {
        "id": r["id"],
        "date": date.fromisoformat(r["date"]),
        "amount_minor": int(r["amount_minor"]),
        "currency": r.get("currency", ""),
        "reference": r.get("reference", "") or "",
        "payout_ref": r.get("payout_ref", "") or "",
        "kind": r.get("kind", "") or "",
        "raw": dict(r),
    }


def _key(l):
    return (l["date"], l["id"])


def reconcile(ours, theirs, config=Config()):
    ours = sorted(ours, key=_key)
    theirs = sorted(theirs, key=_key)
    used_o, used_t = set(), set()
    matches = []

    def take(o, t, tier, rule):
        used_o.add(o["id"])
        used_t.add(t["id"])
        matches.append({"ours": o["id"], "theirs": t["id"], "tier": tier, "rule": rule})

    # Tier 1: reference + amount + currency
    for o in ours:
        if not o["reference"]:
            continue
        for t in theirs:
            if (t["id"] not in used_t and o["reference"] == t["reference"]
                    and o["amount_minor"] == t["amount_minor"]
                    and o["currency"] == t["currency"]):
                take(o, t, 1, "reference")
                break

    # Tier 2: amount + currency, date within window, earliest first
    for o in ours:
        if o["id"] in used_o:
            continue
        for t in theirs:
            if (t["id"] not in used_t
                    and o["amount_minor"] == t["amount_minor"]
                    and o["currency"] == t["currency"]
                    and abs((o["date"] - t["date"]).days) <= config.window_days):
                take(o, t, 2, "amount_date_window")
                break

    # Tier 3 (named rule): payout = captures + booked fee lines, grouped by payout_ref
    for t in theirs:
        if t["id"] in used_t or not t["reference"]:
            continue
        group = [o for o in ours if o["id"] not in used_o
                 and o["payout_ref"] == t["reference"] and o["currency"] == t["currency"]]
        if group and sum(o["amount_minor"] for o in group) == t["amount_minor"]:
            for o in group:
                used_o.add(o["id"])
                matches.append({"ours": o["id"], "theirs": t["id"], "tier": 3,
                                "rule": "payout_equals_captures_plus_fees"})
            used_t.add(t["id"])

    breaks = []
    for side, lines, used in (("ours", ours, used_o), ("theirs", theirs, used_t)):
        for l in lines:
            if l["id"] in used:
                continue
            breaks.append({
                "id": f"brk-{side}-{l['id']}",
                "side": side,
                "line_id": l["id"],
                "amount_minor": l["amount_minor"],
                "currency": l["currency"],
                "date": l["date"].isoformat(),
                # we only have evidence of absence on the other side
                "reason": "missing_theirs" if side == "ours" else "missing_ours",
                "owner": config.owner,
            })

    # Proposed only: a person approves and posts, referencing break_id.
    proposed = [{
        "break_id": b["id"],
        "amount_minor": -b["amount_minor"] if b["side"] == "ours" else b["amount_minor"],
        "currency": b["currency"],
        "status": "proposed",
        "requires_approval": True,
    } for b in breaks]

    unknown = sum(abs(b["amount_minor"]) for b in breaks if b["reason"] == "unknown")
    by_reason = {}
    for b in breaks:
        by_reason[b["reason"]] = by_reason.get(b["reason"], 0) + 1
    total = len(ours) + len(theirs)
    matched_ids = len(used_o) + len(used_t)
    metrics = {
        "match_rate_count": matched_ids / total if total else 1.0,
        "breaks_by_reason": by_reason,
        "amount_unknown_minor": unknown,
    }
    return RunResult(matches, breaks, proposed, metrics)


def _hash(lines):
    blob = json.dumps([l["raw"] for l in sorted(lines, key=_key)], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def write_run_record(path, ours, theirs, config, result, run_at):
    """Immutable record: opened with 'x' so an existing run is never overwritten."""
    record = {
        "run_at": run_at,
        "config": vars(config) if hasattr(config, "__dict__") else dict(config.__dict__),
        "input_hashes": {"ours": _hash(ours), "theirs": _hash(theirs)},
        "matches": result.matches,
        "breaks": result.breaks,
        "proposed_adjustments": result.proposed_adjustments,
        "metrics": result.metrics,
    }
    with open(path, "x") as f:
        json.dump(record, f, indent=2, sort_keys=True)
    return record
