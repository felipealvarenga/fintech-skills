from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    amount: Decimal
    reference: str = ""
    description: str = ""


@dataclass(frozen=True)
class Match:
    ledger: Transaction
    bank: Transaction
    kind: str  # "exact" | "fuzzy" | "amount_mismatch"

    @property
    def difference(self) -> Decimal:
        return self.ledger.amount - self.bank.amount


@dataclass
class ReconciliationResult:
    matched: list[Match] = field(default_factory=list)
    amount_mismatches: list[Match] = field(default_factory=list)
    unmatched_ledger: list[Transaction] = field(default_factory=list)
    unmatched_bank: list[Transaction] = field(default_factory=list)

    @property
    def ledger_total(self) -> Decimal:
        return (
            sum((m.ledger.amount for m in self.matched), Decimal(0))
            + sum((m.ledger.amount for m in self.amount_mismatches), Decimal(0))
            + sum((t.amount for t in self.unmatched_ledger), Decimal(0))
        )

    @property
    def bank_total(self) -> Decimal:
        return (
            sum((m.bank.amount for m in self.matched), Decimal(0))
            + sum((m.bank.amount for m in self.amount_mismatches), Decimal(0))
            + sum((t.amount for t in self.unmatched_bank), Decimal(0))
        )

    @property
    def variance(self) -> Decimal:
        return self.ledger_total - self.bank_total

    @property
    def match_rate(self) -> float:
        total = (
            len(self.matched)
            + len(self.amount_mismatches)
            + len(self.unmatched_ledger)
        )
        return len(self.matched) / total if total else 1.0
