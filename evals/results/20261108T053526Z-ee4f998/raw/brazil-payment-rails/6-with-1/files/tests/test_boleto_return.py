import sys, os
from datetime import date
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from boleto_return import apply_return, expected_amount_minor


class FakeDB:
    def __init__(self, invoices):
        self.invoices = invoices
        self.paid = []

    def query_all(self, sql, params):
        key = params[0]
        return [i for i in self.invoices if (i.nosso_numero.lstrip("0") or "0") == key]

    def execute(self, sql, params):
        self.paid.append(params[0])


def inv(**kw):
    d = dict(id=1, nosso_numero="000123", amount_minor=100_000, status="pending",
             due_date=date(2026, 11, 2), multa_bps=200, juros_monthly_bps=100)
    d.update(kw)
    return NS(**d)


def test_on_time_exact_amount_paid():
    db = FakeDB([inv()])
    apply_return(db, [dict(nosso_numero="123", paid_minor=100_000, paid_on=date(2026, 11, 2))])
    assert db.paid == [1]


def test_late_includes_multa_and_juros():
    # 2% = 2000; 1%/month * 3 days / 30 = 100
    assert expected_amount_minor(inv(), date(2026, 11, 5)) == 102_100
    db = FakeDB([inv()])
    apply_return(db, [dict(nosso_numero="000123", paid_minor=102_100, paid_on=date(2026, 11, 5))])
    assert db.paid == [1]


def test_late_with_original_amount_goes_to_review():
    db = FakeDB([inv()])
    review = apply_return(db, [dict(nosso_numero="000123", paid_minor=100_000, paid_on=date(2026, 11, 5))])
    assert db.paid == [] and len(review) == 1


def test_due_on_weekend_grace():
    weekday = lambda d: d.weekday() < 5
    i = inv(due_date=date(2026, 11, 7))  # Saturday
    assert expected_amount_minor(i, date(2026, 11, 9), weekday) == 100_000


def test_leading_zeros_and_duplicate():
    db = FakeDB([inv(status="paid")])
    apply_return(db, [dict(nosso_numero="123", paid_minor=100_000, paid_on=date(2026, 11, 2))])
    assert db.paid == []
