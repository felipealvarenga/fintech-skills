from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Txn:
    id: str
    date: date
    amount: Decimal
    reference: str
    description: str = ""


@dataclass(frozen=True)
class Match:
    bank: Txn
    ledger: Txn
    kind: str  # "reference" | "fuzzy" | "amount_mismatch"
    difference: Decimal  # bank.amount - ledger.amount


@dataclass
class Result:
    matches: list
    unmatched_bank: list
    unmatched_ledger: list
