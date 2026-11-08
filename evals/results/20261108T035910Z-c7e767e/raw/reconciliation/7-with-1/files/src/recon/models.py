from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

REASONS = ("timing", "fee", "fx", "missing_ours", "missing_theirs", "duplicate", "unknown")
OWNERS = {
    "timing": "finance-ops",
    "fee": "accounting",
    "fx": "treasury",
    "missing_ours": "payments-eng",
    "missing_theirs": "finance-ops",
    "duplicate": "payments-eng",
    "unknown": "finance-ops",
}


@dataclass(frozen=True)
class Line:
    source: str
    id: str
    date: date
    amount_minor: int
    currency: str
    reference: str = ""
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True)
class Config:
    """Explicit, reviewed parameters. No amount tolerance exists by design."""

    as_of: date                      # run date; passed in so reconcile() has no clock
    date_window_days: int = 2        # business days; needs finance approval to change
    enable_payout_rule: bool = True  # tier 3: payout = captures - fees
    unknown_page_after_days: int = 2
    min_match_rate_count: float = 0.98
    min_match_rate_amount: float = 0.98
    max_oldest_break_days: int = 5
    max_unknown_minor: int = 0


@dataclass(frozen=True)
class Match:
    tier: int
    rule: str
    ours: tuple[str, ...]
    theirs: tuple[str, ...]
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class Break:
    side: str          # "ours" | "theirs"
    line_id: str
    reason: str
    owner: str
    age_days: int
    amount_minor: int
    currency: str
    note: str = ""


@dataclass(frozen=True)
class RunResult:
    matches: tuple[Match, ...]
    breaks: tuple[Break, ...]
    metrics: dict[str, Any]
    alerts: tuple[str, ...]
