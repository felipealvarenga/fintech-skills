from __future__ import annotations

from collections import Counter


def compute_metrics(ours, theirs, matches, breaks) -> dict:
    by_id = {l.id: l for l in [*ours, *theirs]}
    total = len(ours) + len(theirs)
    matched_ids = [i for m in matches for i in (*m.ours, *m.theirs)]
    total_amt = sum(abs(l.amount_minor) for l in by_id.values())
    matched_amt = sum(abs(by_id[i].amount_minor) for i in matched_ids)
    reasons = Counter(b.reason for b in breaks)
    return {
        "lines_total": total,
        "lines_matched": len(matched_ids),
        "match_rate_count": len(matched_ids) / total if total else 1.0,
        "match_rate_amount": matched_amt / total_amt if total_amt else 1.0,
        "breaks_by_reason": dict(sorted(reasons.items())),
        "oldest_break_days": max((b.age_days for b in breaks), default=0),
        "unknown_amount_minor": sum(abs(b.amount_minor) for b in breaks if b.reason == "unknown"),
    }
