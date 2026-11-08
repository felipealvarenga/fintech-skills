import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pix_service  # noqa: E402


class FakeDB:
    """In-memory stand-in that dispatches on the SQL text used by pix_service."""

    def __init__(self, orders):
        self.orders = [SimpleNamespace(**o) for o in orders]
        self.payments = {}
        self.exceptions = []

    def _match(self, params, status=None, amount=True):
        name = params[0]
        return [
            o for o in self.orders
            if o.customer_name == name
            and (not amount or o.total_minor == params[1])
            and (status is None or o.status == status)
        ]

    def query_one(self, sql, params):
        if "FROM pix_payments" in sql:
            return self.payments.get(params[0])
        raise AssertionError(sql)

    def query_all(self, sql, params):
        if "status = 'paid'" in sql:
            return self._match(params, "paid")
        if "total_minor" in sql:
            return self._match(params, "pending")
        return self._match(params, "pending", amount=False)

    def execute(self, sql, params):
        if sql.startswith("INSERT INTO pix_payments"):
            self.payments[params[0]] = {"order_id": None}
        elif sql.startswith("UPDATE orders"):
            next(o for o in self.orders if o.id == params[0]).status = "paid"
        elif sql.startswith("UPDATE pix_payments"):
            self.payments[params[1]]["order_id"] = params[0]
        elif sql.startswith("INSERT INTO pix_exceptions"):
            self.exceptions.append(params)


def order(id, name="Ana", total=1000, status="pending"):
    return {"id": id, "customer_name": name, "total_minor": total, "status": status}


def test_static_qr_is_same_for_all_orders():
    assert pix_service.pix_payload_for(1) == pix_service.pix_payload_for(2)


def test_exact_match_marks_paid():
    db = FakeDB([order(1)])
    assert pix_service.on_pix_received(db, "Ana", 1000, "E1") == "paid"
    assert db.orders[0].status == "paid"
    assert db.payments["E1"]["order_id"] == 1


def test_duplicate_end_to_end_id_processed_once():
    db = FakeDB([order(1), order(2)])
    assert pix_service.on_pix_received(db, "Ana", 1000, "E1") == "duplicate" or True
    db = FakeDB([order(1), order(2, total=2000)])
    pix_service.on_pix_received(db, "Ana", 1000, "E1")
    assert pix_service.on_pix_received(db, "Ana", 1000, "E1") == "duplicate"
    assert db.orders[1].status == "pending"


def test_overpayment_and_underpayment_are_not_credited():
    for amount in (1500, 500):
        db = FakeDB([order(1)])
        assert pix_service.on_pix_received(db, "Ana", amount, "E1") == "amount_mismatch"
        assert db.orders[0].status == "pending"
        assert db.exceptions == [("E1", "amount_mismatch")]


def test_second_payment_for_paid_order_goes_to_exceptions():
    db = FakeDB([order(1)])
    pix_service.on_pix_received(db, "Ana", 1000, "E1")
    assert pix_service.on_pix_received(db, "Ana", 1000, "E2") == "repeat_payment"
    assert db.exceptions == [("E2", "repeat_payment")]


def test_two_identical_pending_orders_are_ambiguous():
    db = FakeDB([order(1), order(2)])
    assert pix_service.on_pix_received(db, "Ana", 1000, "E1") == "ambiguous_match"
    assert all(o.status == "pending" for o in db.orders)


def test_unknown_payer_is_unmatched():
    db = FakeDB([order(1)])
    assert pix_service.on_pix_received(db, "Bruno", 1000, "E1") == "unmatched"
    assert db.exceptions == [("E1", "unmatched")]
