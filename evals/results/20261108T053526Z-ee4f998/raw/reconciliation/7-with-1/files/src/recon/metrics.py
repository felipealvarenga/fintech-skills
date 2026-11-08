"""The four dashboard metrics (rule 9) and their threshold alerts."""
from __future__ import annotations

from collections import Counter

from .models import REASONS, Break, Config, Line, Match


def compute_metrics(lines: list[Line], matches: list[Match], breaks: list[Break], cfg: Config):
    by_id = {l.id: l for l in lines}
    matched_ids = {i for m in matches for i in (*m.ours, *m.theirs)}
    total_n = len(lines)
    total_amt = sum(abs(l.amount_minor) for l in lines)
    matched_amt = sum(abs(by_id[i].amount_minor) for i in matched_ids if i in by_id)

    counts = Counter(b.reason for b in breaks)
    unknown_amt = sum(abs(b.amount_minor) for b in breaks if b.reason == "unknown")
    metrics = {
        "match_rate_count": (len(matched_ids) / total_n) if total_n else 1.0,
        "match_rate_amount": (matched_amt / total_amt) if total_amt else 1.0,
        "breaks_by_reason": {r: counts.get(r, 0) for r in REASONS},
        "oldest_open_break_days": max((b.age_days for b in breaks), default=0),
        "unknown_amount_minor": unknown_amt,
    }

    alerts: list[str] = []
    if metrics["match_rate_count"] < cfg.min_match_rate_count:
        alerts.append(f"match rate by count {metrics['match_rate_count']:.1%} below {cfg.min_match_rate_count:.0%}")
    if metrics["match_rate_amount"] < cfg.min_match_rate_amount:
        alerts.append(f"match rate by amount {metrics['match_rate_amount']:.1%} below {cfg.min_match_rate_amount:.0%}")
    if metrics["oldest_open_break_days"] > cfg.max_oldest_break_days:
        alerts.append(f"oldest open break {metrics['oldest_open_break_days']}d exceeds {cfg.max_oldest_break_days}d")
    if unknown_amt > cfg.max_unknown_amount_minor:
        alerts.append(f"unknown amount {unknown_amt} exceeds {cfg.max_unknown_amount_minor}")
    # Page a person: unknown breaks older than the window.
    for b in breaks:
        if b.reason == "unknown" and b.age_days > cfg.window_business_days:
            alerts.append(f"PAGE {b.owner}: unknown break {b.line_id} aged {b.age_days}d")
    return metrics, alerts
