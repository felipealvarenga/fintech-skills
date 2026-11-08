import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from types import SimpleNamespace as NS

import qbo_sync


class FakeDB:
    def __init__(self, row):
        self.row = row
        self.executed = []

    def query(self, sql, params=()):
        return [self.row] if self.row else []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))


class FakeQBO:
    def __init__(self, token="3", void_error=None):
        self.token = token
        self.void_error = void_error
        self.voids = []

    def get_invoice(self, qbo_id):
        return {"Id": qbo_id, "SyncToken": self.token}

    def void_invoice(self, qbo_id, sync_token, requestid):
        if self.void_error:
            raise self.void_error
        self.voids.append((qbo_id, sync_token, requestid))
        return {"Id": qbo_id, "SyncToken": str(int(sync_token) + 1)}


def pair(status="pushed", token="3"):
    return NS(our_id="inv1", qbo_id="99", sync_token=token, status=status)


def test_delete_becomes_void_linked_to_original():
    db, qbo = FakeDB(pair()), FakeQBO()
    assert qbo_sync.void_invoice(db, qbo, "inv1") == "voided"
    assert qbo.voids == [("99", "3", "void-inv-inv1")]
    assert "voided" in db.executed[0][0]  # our row keeps the qbo_id link


def test_second_call_is_noop():
    db, qbo = FakeDB(pair(status="voided")), FakeQBO()
    assert qbo_sync.void_invoice(db, qbo, "inv1") == "voided"
    assert qbo.voids == []


def test_unsynced_invoice_is_ignored():
    assert qbo_sync.void_invoice(FakeDB(None), FakeQBO(), "inv1") == "not_synced"


def test_stale_token_records_conflict_and_does_not_void():
    db, qbo = FakeDB(pair(token="3")), FakeQBO(token="4")
    assert qbo_sync.void_invoice(db, qbo, "inv1") == "conflict"
    assert qbo.voids == []


def test_closed_period_flags_review_without_retry():
    db, qbo = FakeDB(pair()), FakeQBO(void_error=qbo_sync.ClosedPeriod())
    assert qbo_sync.void_invoice(db, qbo, "inv1") == "needs_review"
