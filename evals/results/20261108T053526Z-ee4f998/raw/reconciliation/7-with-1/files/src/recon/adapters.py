"""One adapter per source, each producing normalized Lines. Raw row is kept."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from .models import Line

_EXPONENT = {"JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}


def to_minor(amount: str, currency: str) -> int:
    exp = _EXPONENT.get(currency, 2)
    d = Decimal(amount.strip())
    scaled = d * (10 ** exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"amount {amount!r} has more precision than {currency} allows")
    return int(scaled)


def ledger_line(row: dict) -> Line:
    """Ledger CSV: entry_id,posted_date,amount,currency,reference,memo,payout_ref"""
    cur = row["currency"].strip().upper()
    return Line(
        source="ledger", id=row["entry_id"].strip(),
        date=date.fromisoformat(row["posted_date"].strip()),
        amount_minor=to_minor(row["amount"], cur), currency=cur,
        reference=row.get("reference", "").strip(), description=row.get("memo", "").strip(),
        kind="payment", group=row.get("payout_ref", "").strip(), raw=dict(row),
    )


_PROCESSOR_KINDS = {"charge": "payment", "payout": "payout", "fee": "fee"}


def processor_line(row: dict) -> Line:
    """Processor CSV: txn_id,date,amount,currency,reference,type,payout_id,description
    Fees are positive magnitudes; payouts are the net amount sent to the bank."""
    cur = row["currency"].strip().upper()
    t = row["type"].strip().lower()
    if t not in _PROCESSOR_KINDS:
        raise ValueError(f"unknown processor type {t!r} in {row.get('txn_id')}")
    return Line(
        source="processor", id=row["txn_id"].strip(),
        date=date.fromisoformat(row["date"].strip()),
        amount_minor=to_minor(row["amount"], cur), currency=cur,
        reference=row.get("reference", "").strip(), description=row.get("description", "").strip(),
        kind=_PROCESSOR_KINDS[t], group=row.get("payout_id", "").strip(), raw=dict(row),
    )


def _load(path: Path, fn) -> list[Line]:
    with open(path, newline="", encoding="utf-8") as f:
        return [fn(r) for r in csv.DictReader(f)]


def load_ledger(path: Path) -> list[Line]:
    return _load(path, ledger_line)


def load_processor(path: Path) -> list[Line]:
    return _load(path, processor_line)
