import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from schedule import Contract, sac_schedule, cet  # noqa: E402

C = Contract(principal_minor=100000, periodic_rate="0.01", periods=12)
FIRST = date(2026, 1, 31)


def test_sac_vectors():
    rows = sac_schedule(C, FIRST)
    assert [r["principal"] for r in rows[:11]] == [8333] * 11
    assert rows[-1]["principal"] == 8337
    assert rows[0]["interest"] == 1000
    assert rows[0]["installment"] == 9333
    assert sum(r["principal"] for r in rows) == 100000
    assert rows[-1]["balance"] == 0


def test_sac_installments_decrease_and_month_end_dates():
    rows = sac_schedule(C, FIRST)
    assert rows[1]["due_date"] == date(2026, 2, 28)
    assert rows[0]["installment"] > rows[10]["installment"]


def test_sac_single_period():
    r = sac_schedule(Contract(100000, "0.01", 1), FIRST)
    assert len(r) == 1 and r[0]["installment"] == 101000


def test_cet_without_fees_matches_rate_scale():
    rows = sac_schedule(C, FIRST)
    base = cet(date(2025, 12, 31), 100000, rows)
    with_fee = cet(date(2025, 12, 31), 100000, rows, upfront_fees_minor=(1500,))
    assert with_fee > base > Decimal("0.12")  # above 1%/month nominal-ish floor
