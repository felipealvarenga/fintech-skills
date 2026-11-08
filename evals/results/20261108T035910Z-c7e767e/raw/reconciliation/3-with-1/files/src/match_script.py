"""Tiered, deterministic matcher plus month-end close.

The job never writes to the ledger. Month end produces matches, breaks and
*proposed* adjustments (status "pending_approval") that reference the break.
A human, or a separately approved rule, posts them.
"""
import csv
import hashlib
import json
from datetime import date

DEFAULT_WINDOW_DAYS = 2  # parameter; needs owner approval (calendar days)


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def normalize(row, source):
    d = row.get("date") or ""
    return {
        "source": source,
        "id": row["id"],
        "date": date.fromisoformat(d) if d else None,
        "amount_minor": int(row["amount_minor"]),
        "currency": row.get("currency", ""),
        "reference": row.get("reference", ""),
        "raw": row,
    }


def _sorted(lines):
    return sorted(lines, key=lambda l: (l["date"] or date.min, l["id"]))


def reconcile(ours, theirs, window_days=DEFAULT_WINDOW_DAYS):
    """Pure function. Returns (matches, unmatched_ours, unmatched_theirs)."""
    ours, theirs = _sorted(ours), _sorted(theirs)
    used_o, used_t, matches = set(), set(), []

    def same_money(o, t):
        return o["amount_minor"] == t["amount_minor"] and o["currency"] == t["currency"]

    # Tier 1: reference + amount + currency
    for o in ours:
        if not o["reference"]:
            continue
        for t in theirs:
            if t["id"] in used_t:
                continue
            if o["reference"] == t["reference"] and same_money(o, t):
                matches.append({"ours": o["id"], "theirs": t["id"], "tier": 1})
                used_o.add(o["id"]); used_t.add(t["id"])
                break

    # Tier 2: amount + currency, date within window, earliest first
    for o in ours:
        if o["id"] in used_o or o["date"] is None:
            continue
        for t in theirs:
            if t["id"] in used_t or t["date"] is None:
                continue
            if same_money(o, t) and abs((o["date"] - t["date"]).days) <= window_days:
                matches.append({"ours": o["id"], "theirs": t["id"], "tier": 2})
                used_o.add(o["id"]); used_t.add(t["id"])
                break

    return (
        matches,
        [o for o in ours if o["id"] not in used_o],
        [t for t in theirs if t["id"] not in used_t],
    )


def _break(line, reason, side):
    return {
        "break_id": f"{side}:{line['id']}",
        "reason": reason,
        "owner": "finance-ops",
        "side": side,
        "line_id": line["id"],
        "amount_minor": line["amount_minor"],
        "currency": line["currency"],
        "date": line["date"].isoformat() if line["date"] else None,
    }


def _propose(brk):
    """Draft correcting entry. Not posted; references the break."""
    sign = 1 if brk["reason"] == "missing_ours" else -1
    return {
        "break_ref": brk["break_id"],
        "amount_minor": sign * brk["amount_minor"],
        "currency": brk["currency"],
        "status": "pending_approval",
        "approved_by": None,
    }


def _hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def month_end(ours_rows, theirs_rows, run_time, window_days=DEFAULT_WINDOW_DAYS):
    """Run over the whole open window; return an immutable-style run record.

    run_time is passed in so the function stays free of clock access.
    Persist the record write-once; do not post proposed_adjustments here.
    """
    ours = [normalize(r, "ours") for r in ours_rows]
    theirs = [normalize(r, "theirs") for r in theirs_rows]
    matches, un_o, un_t = reconcile(ours, theirs, window_days)

    breaks = [_break(o, "missing_theirs", "ours") for o in un_o]
    breaks += [_break(t, "missing_ours", "theirs") for t in un_t]
    return {
        "run_time": run_time,
        "params": {"window_days": window_days},
        "input_hashes": {"ours": _hash(ours_rows), "theirs": _hash(theirs_rows)},
        "matches": matches,
        "breaks": breaks,
        "proposed_adjustments": [_propose(b) for b in breaks],
        "metrics": {
            "matched_count": len(matches),
            "break_count": len(breaks),
            "unknown_amount_minor": sum(abs(b["amount_minor"]) for b in breaks),
        },
    }
