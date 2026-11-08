import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from .models import Txn

REQUIRED = {"id", "date", "amount", "reference"}


def load_csv(path):
    """Load transactions. Columns: id,date(YYYY-MM-DD),amount,reference[,description]."""
    txns = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        for n, row in enumerate(reader, start=2):
            try:
                txns.append(
                    Txn(
                        id=row["id"].strip(),
                        date=date.fromisoformat(row["date"].strip()),
                        amount=Decimal(row["amount"].strip()),
                        reference=row["reference"].strip().upper(),
                        description=(row.get("description") or "").strip(),
                    )
                )
            except (ValueError, InvalidOperation) as e:
                raise ValueError(f"{path} line {n}: {e}") from e
    return txns
