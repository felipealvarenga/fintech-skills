"""Normalized line shape, config and result types. No behaviour here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Reason codes (rule 5). Only `unknown` older than the window pages a person.
REASONS = ("timing", "fee", "fx", "missing_ours", "missing_theirs", "duplicate", "unknown")


@dataclass(frozen=True)
class Line:
    source: str              # "ledger" | "processor" | ...
    id: str
    date: date
    amount_minor: int
    currency: str
    reference: str = ""
    description: str = ""
    kind: str = "payment"    # "payment" | "payout" | "fee"
    group: str = ""          # payout reference this line belongs to (tier 3)
    raw: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True)
class Config:
    as_of: date                          # passed in: the function never reads a clock
    window_business_days: int = 2        # tier 2 date window; needs finance approval
    owners: dict[str, str] = field(default_factory=lambda: {
        "timing": "recon-bot",
        "fee": "accounting",
        "fx": "treasury",
        "missing_ours": "accounting",
        "missing_theirs": "payments-ops",
        "duplicate": "payments-ops",
        "unknown": "finance-on-call",
    })
    # Dashboard thresholds (rule 9)
    min_match_rate_count: float = 0.98
    min_match_rate_amount: float = 0.98
    max_oldest_break_days: int = 5
    max_unknown_amount_minor: int = 0


@dataclass(frozen=True)
class Match:
    tier: str                    # "tier1_reference" | "tier2_date_window" | "tier3:<rule name>"
    ours: tuple[str, ...]        # ids
    theirs: tuple[str, ...]
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class Break:
    side: str                    # "ours" | "theirs"
    line_id: str
    reason: str
    owner: str
    age_days: int
    amount_minor: int
    currency: str
    detail: str = ""


@dataclass(frozen=True)
class RunResult:
    matches: tuple[Match, ...]
    breaks: tuple[Break, ...]
    metrics: dict[str, Any]
    alerts: tuple[str, ...]
