import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from qbo_sync import ClosedPeriodError, void_invoice


class FakeDB:
    def __init__(self, pair):
        self.pair = pair
        self.executed = []

    def query_one(self, sql, *args):
        return self.pair

    def execute(self, sql, *args):
        self.executed.append((sql, args))


class FakeQBO:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def void_invoice(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return {"SyncToken": "3"}


def pair(status="synced"):
    return SimpleNamespace(qbo_id="145", sync_token="2", status=status)


def test_delete_becomes_void_linked_to_original():
    db, qbo = FakeDB(pair()), FakeQBO()
    assert void_invoice(db, qbo, "inv_1") == "voided"
    assert qbo.calls == [{"qbo_id": "145", "sync_token": "2", "request_id": "void-invoice-inv_1"}]
    assert "status = 'voided'" in db.executed[0][0]
    assert db.executed[0][1] == ("3", "inv_1")


def test_unsynced_invoice_is_noop():
    db, qbo = FakeDB(None), FakeQBO()
    assert void_invoice(db, qbo, "inv_1") == "not_synced"
    assert qbo.calls == []


def test_repeat_does_not_void_twice():
    db, qbo = FakeDB(pair("voided")), FakeQBO()
    assert void_invoice(db, qbo, "inv_1") == "already_voided"
    assert qbo.calls == []


def test_closed_period_queues_for_review_without_retry():
    db, qbo = FakeDB(pair()), FakeQBO(error=ClosedPeriodError())
    assert void_invoice(db, qbo, "inv_1") == "needs_review"
    assert len(qbo.calls) == 1
    assert "needs_review" in db.executed[0][0]


def test_stale_sync_token_propagates_not_overwritten():
    db, qbo = FakeDB(pair()), FakeQBO(error=RuntimeError("5010 stale object"))
    with pytest.raises(RuntimeError):
        void_invoice(db, qbo, "inv_1")
    assert db.executed == []
