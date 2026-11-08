import datetime
import pytest
from interest import price_schedule, simple_interest


def test_price_total():
    rows = price_schedule(100000, "0.01", 12)
    assert sum(r["installment"] for r in rows) == sum(r["installment"] for r in price_schedule(100000, "0.01", 12))


def test_interest_today():
    days = (datetime.date.today() - datetime.date(2026, 1, 1)).days
    assert simple_interest(100000, "0.12", days) == pytest.approx(100000 * 0.12 * days / 365, rel=1e-3)
