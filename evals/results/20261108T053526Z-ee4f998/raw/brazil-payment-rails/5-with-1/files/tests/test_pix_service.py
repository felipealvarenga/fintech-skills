import sys, pathlib, types
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
import pix_service as ps


class Row(types.SimpleNamespace):
    pass


class FakeDB:
    """Minimal fake: answers query_one by table keyword; records executes."""
    def __init__(self, **rows):
        self.rows, self.executed = rows, []

    def query_one(self, sql, params=()):
        for key in ("pix_disputes", "pix_payments", "pix_charges", "orders"):
            if f"FROM {key}" in sql:
                return self.rows.get(key)

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "INSERT INTO pix_payments" in sql:
            self.rows["pix_payments"] = Row(txid=params[1], amount_minor=params[2],
                                            refunded_minor=0, status=params[3])


class FakePSP:
    def __init__(self, e2e="E1", amount=1000, status="CONCLUIDA"):
        self.remote = Row(status=status, pix=[Row(end_to_end_id=e2e, amount_minor=amount)])
        self.devolucoes = []

    def get_charge(self, txid):
        return self.remote

    def create_devolucao(self, e2e, id, amount_minor):
        self.devolucoes.append((e2e, amount_minor))


def test_duplicate_end_to_end_id_processed_once():
    db = FakeDB(pix_payments=Row(refunded_minor=0, amount_minor=1000))
    assert ps.on_pix_received(db, FakePSP(), "tx", "E1", 1000) == "duplicate"
    assert db.executed == []


def test_expired_charge_paid_is_refunded_not_fulfilled():
    db = FakeDB(pix_charges=Row(status="expired", amount_minor=1000, order_id=1))
    psp = FakePSP()
    ps.on_pix_received(db, psp, "tx", "E1", 1000)
    assert psp.devolucoes == [("E1", 1000)]
    assert not any("status = 'paid'" in s for s, _ in db.executed)


def test_open_charge_marks_order_paid():
    db = FakeDB(pix_charges=Row(status="open", amount_minor=1000, order_id=1))
    assert ps.on_pix_received(db, FakePSP(), "tx", "E1", 1000) == "paid"


def test_partial_devolucao_accumulates():
    db = FakeDB(pix_payments=Row(refunded_minor=300, amount_minor=1000))
    psp = FakePSP()
    ps.refund(db, psp, "E1", 200)
    assert db.executed[-1][1][0] == 500
    try:
        ps.refund(db, psp, "E1", 600)
        assert False
    except ValueError:
        pass


def _med_db(shipped):
    return FakeDB(
        pix_payments=Row(txid="tx", amount_minor=1000, refunded_minor=0),
        pix_charges=Row(order_id=7),
        orders=Row(id=7, shipped_at="2026-11-01" if shipped else None),
    )


def test_med_after_shipping_opens_recovery_case():
    db = _med_db(True)
    db.rows["pix_disputes"] = None
    assert ps.on_med_claim_opened(db, "E1") == "recovery_opened"
    assert any("recovery_cases" in s for s, _ in db.executed)


def test_med_before_shipping_holds_fulfilment():
    db = _med_db(False)
    assert ps.on_med_claim_opened(db, "E1") == "held_before_shipping"


def test_med_claim_duplicate_is_noop():
    db = _med_db(True)
    db.rows["pix_disputes"] = Row()
    assert ps.on_med_claim_opened(db, "E1") == "duplicate"


def test_med_partial_returns_over_time_then_full():
    db = FakeDB(pix_payments=Row(txid="tx", amount_minor=1000, refunded_minor=400))
    ps.on_med_funds_returned(db, "E1", 600)
    assert any("funds_returned" in s for s, _ in db.executed)
