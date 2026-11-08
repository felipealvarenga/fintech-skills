import sqlite3
import sys
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pix_service as ps  # noqa: E402

Order = namedtuple("Order", "id total_minor")
E2E = "E" + "1" * 31


class DB:
    def __init__(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
            CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT);
            CREATE TABLE pix_charges (txid TEXT PRIMARY KEY, order_id INT, amount_minor INT, payload TEXT,
                status TEXT, end_to_end_id TEXT UNIQUE, expires_at TEXT);
            CREATE TABLE pix_payments (end_to_end_id TEXT PRIMARY KEY, txid TEXT, amount_minor INT, outcome TEXT);
            INSERT INTO orders VALUES (1, 'pending');
        """)

    def execute(self, sql, params=()):
        self.c.execute(sql.replace("%s", "?"), params)

    def query_one(self, sql, params=()):
        r = self.c.execute(sql.replace("%s", "?"), params).fetchone()
        return namedtuple("Row", r.keys())(*r) if r else None


class FakePSP:
    def __init__(self):
        self.status, self.refunds, self.amount = "CONCLUIDA", [], None

    def create_immediate_charge(self, txid, amount_minor, expires_in):
        self.amount = amount_minor
        return f"BRCODE-{txid}"

    def get_charge(self, txid):
        return {"status": self.status, "amount_minor": self.amount, "paid_end_to_end_ids": [E2E]}

    def refund(self, e2e, refund_id, amount_minor):
        self.refunds.append((e2e, refund_id, amount_minor))


def setup():
    db, psp = DB(), FakePSP()
    txid = ps.create_charge(db, psp, Order(1, 10_000))["txid"]
    return db, psp, txid


def order_status(db):
    return db.query_one("SELECT status FROM orders WHERE id = 1").status


def test_each_order_gets_its_own_charge_and_reuses_active_one():
    db, psp, txid = setup()
    assert ps.create_charge(db, psp, Order(1, 10_000))["txid"] == txid
    assert 26 <= len(txid) <= 35


def test_paid_marks_order_and_stores_end_to_end_id():
    db, psp, txid = setup()
    assert ps.on_pix_received(db, psp, txid, E2E, 10_000) == "paid"
    assert order_status(db) == "paid"
    assert db.query_one("SELECT end_to_end_id FROM pix_charges").end_to_end_id == E2E


def test_duplicate_end_to_end_id_processed_once():
    db, psp, txid = setup()
    ps.on_pix_received(db, psp, txid, E2E, 10_000)
    assert ps.on_pix_received(db, psp, txid, E2E, 10_000) == "duplicate"
    assert psp.refunds == []


def test_unconfirmed_by_api_does_not_fulfil():
    db, psp, txid = setup()
    psp.status = "ATIVA"
    assert ps.on_pix_received(db, psp, txid, E2E, 10_000) == "refunded"
    assert order_status(db) == "pending"


def test_paid_after_expiry_is_refunded():
    db, psp, txid = setup()
    ps.expire_charges(db, datetime.now(timezone.utc) + timedelta(hours=1))
    assert ps.on_pix_received(db, psp, txid, E2E, 10_000) == "refunded"
    assert order_status(db) == "pending"
    assert psp.refunds == [(E2E, "r" + E2E, 10_000)]


def test_overpayment_and_underpayment_are_refunded_not_credited():
    for amount in (12_000, 8_000):
        db, psp, txid = setup()
        assert ps.on_pix_received(db, psp, txid, E2E, amount) == "refunded"
        assert order_status(db) == "pending"


def test_second_payment_on_paid_charge_is_refunded():
    db, psp, txid = setup()
    ps.on_pix_received(db, psp, txid, E2E, 10_000)
    other = "E" + "2" * 31
    psp.get_charge = lambda t: {"status": "CONCLUIDA", "amount_minor": 10_000,
                                "paid_end_to_end_ids": [E2E, other]}
    assert ps.on_pix_received(db, psp, txid, other, 10_000) == "refunded"
    assert psp.refunds[0][0] == other


def test_unknown_txid_is_recorded_not_matched_by_amount():
    db, psp, _ = setup()
    assert ps.on_pix_received(db, psp, "x" * 32, E2E, 10_000) == "unknown_charge"
    assert order_status(db) == "pending"
