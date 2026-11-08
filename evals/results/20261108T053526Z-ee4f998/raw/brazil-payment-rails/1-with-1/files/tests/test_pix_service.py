import os
import sqlite3
import sys
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pix_service as px  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
Order = namedtuple("Order", "id total_minor")


class Db:
    """sqlite adapter exposing the query_one/execute API with %s placeholders."""

    def __init__(self):
        self.c = sqlite3.connect(":memory:")
        self.c.executescript(open(os.path.join(ROOT, "sql", "pix.sql")).read())
        self.c.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT, total_minor INT)")
        self.c.execute("INSERT INTO orders VALUES (1, 'pending', 5000)")

    def query_one(self, sql, params=()):
        cur = self.c.execute(sql.replace("%s", "?"), params)
        row = cur.fetchone()
        if row is None:
            return None
        return namedtuple("Row", [d[0] for d in cur.description])(*row)

    def execute(self, sql, params=()):
        self.c.execute(sql.replace("%s", "?"), params)


class FakePsp:
    def __init__(self):
        self.status, self.amount, self.refunds = "CONCLUIDA", 5000, []

    def create_charge(self, txid, amount_minor, expires_in_s):
        return "BRCODE-" + txid

    def get_charge(self, txid):
        return {"status": self.status, "amount_minor": self.amount}

    def refund(self, e2e, refund_id, amount_minor):
        self.refunds.append((e2e, amount_minor))


@pytest.fixture
def env():
    db, psp = Db(), FakePsp()
    charge = px.create_pix_charge(db, psp, Order(1, 5000))
    return db, psp, charge


def order_status(db):
    return db.query_one("SELECT status FROM orders WHERE id = 1").status


def ev(txid, e2e="E1", amount=5000):
    return {"txid": txid, "end_to_end_id": e2e, "amount_minor": amount}


def test_charge_creation_leaves_order_pending(env):
    db, _, charge = env
    assert order_status(db) == "pending"
    assert len(charge["txid"]) == 32


def test_paid_webhook_marks_order_paid(env):
    db, psp, c = env
    assert px.on_pix_received(db, psp, ev(c["txid"])) == "paid"
    assert order_status(db) == "paid"


def test_duplicate_end_to_end_id_processed_once(env):
    db, psp, c = env
    px.on_pix_received(db, psp, ev(c["txid"]))
    assert px.on_pix_received(db, psp, ev(c["txid"])) == "duplicate"
    assert psp.refunds == []


def test_unconfirmed_by_psp_is_not_fulfilled(env):
    db, psp, c = env
    psp.status = "ATIVA"
    assert px.on_pix_received(db, psp, ev(c["txid"])) == "refunded"
    assert order_status(db) == "pending"


def test_expired_charge_paid_is_refunded(env):
    db, psp, c = env
    px.expire_charges(db, now=datetime.now(timezone.utc) + timedelta(hours=1))
    assert px.on_pix_received(db, psp, ev(c["txid"])) == "refunded"
    assert psp.refunds == [("E1", 5000)]
    assert order_status(db) == "pending"


def test_second_payment_on_paid_charge_is_refunded(env):
    db, psp, c = env
    px.on_pix_received(db, psp, ev(c["txid"], "E1"))
    assert px.on_pix_received(db, psp, ev(c["txid"], "E2")) == "refunded"
    assert psp.refunds == [("E2", 5000)]


def test_overpayment_and_underpayment_refunded_not_credited(env):
    db, psp, c = env
    assert px.on_pix_received(db, psp, ev(c["txid"], "E1", 6000)) == "refunded"
    assert px.on_pix_received(db, psp, ev(c["txid"], "E2", 4000)) == "refunded"
    assert order_status(db) == "pending"


def test_static_qr_payment_without_txid_goes_to_exceptions_not_credit(env):
    db, psp, _ = env
    assert px.on_pix_received(db, psp, ev(None, "E9")) == "exception"
    assert order_status(db) == "pending"
    assert db.query_one("SELECT 1 AS x FROM pix_exceptions WHERE end_to_end_id = 'E9'")


def test_name_and_amount_never_match(env):
    db, psp, _ = env
    e = {"txid": "unknown", "end_to_end_id": "E5", "amount_minor": 5000, "payer_name": "X"}
    assert px.on_pix_received(db, psp, e) == "exception"
    assert order_status(db) == "pending"


def test_partial_devolucao_updates_balance(env):
    db, psp, c = env
    px.on_pix_received(db, psp, ev(c["txid"]))
    px.refund_pix(db, psp, "E1", 1500)
    px.refund_pix(db, psp, "E1", 500)
    assert db.query_one("SELECT refunded_minor FROM pix_payments WHERE end_to_end_id='E1'").refunded_minor == 2000
    with pytest.raises(ValueError):
        px.refund_pix(db, psp, "E1", 3100)
