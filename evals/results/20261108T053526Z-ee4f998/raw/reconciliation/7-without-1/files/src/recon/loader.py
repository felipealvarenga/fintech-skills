from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Transaction

REQUIRED = {"id", "date", "amount"}


def load_csv(path: str | Path) -> list[Transaction]:
    """Load transactions from CSV with columns: id,date(YYYY-MM-DD),amount[,reference,description]."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = []
        for n, row in enumerate(reader, start=2):
            try:
                rows.append(
                    Transaction(
                        id=row["id"].strip(),
                        date=date.fromisoformat(row["date"].strip()),
                        amount=Decimal(row["amount"].strip().replace(",", "")),
                        reference=(row.get("reference") or "").strip(),
                        description=(row.get("description") or "").strip(),
                    )
                )
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"{path}:{n}: invalid row ({exc})") from exc
        return rows
