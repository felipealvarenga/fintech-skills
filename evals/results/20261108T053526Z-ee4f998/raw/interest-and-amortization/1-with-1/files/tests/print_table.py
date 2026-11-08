import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from amortization import Contract, price_schedule  # noqa: E402

rows = price_schedule(Contract(D("1000.00"), D("0.01"), 12, date(2026, 12, 8)))
print(f"{'#':>2} {'Due':<10} {'Installment':>11} {'Interest':>9} {'Principal':>10} {'Balance':>9}")
for r in rows:
    print(f"{r.period:>2} {r.due_date!s:<10} {r.installment:>11} {r.interest:>9} {r.principal:>10} {r.balance:>9}")
print(f"Total paid: {sum(r.installment for r in rows)}  Interest: {sum(r.interest for r in rows)}")
