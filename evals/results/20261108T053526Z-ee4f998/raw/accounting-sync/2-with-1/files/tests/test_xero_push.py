import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import xero_push  # noqa: E402


class FakeDB:
    def __init__(self, rows):
        self.rows, self.executed = rows, []

    def query(self, sql):
        return self.rows

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def ran(self, fragment):
        return [e for e in self.executed if fragment in e[0]]


class FakeXero:
    def __init__(self, remote):
        self.remote, self.updates = remote, []

    def get_bank_transaction(self, xero_id):
        return self.remote

    def update_bank_transaction(self, xero_id, payload):
        self.updates.append((xero_id, payload))
        return {"UpdatedDateUTC": "T2"}


def expense(**kw):
    base = dict(id=1, xero_id="x1", account_code="200", xero_updated_utc="T1",
                last_pushed_account_code="200")
    base.update(kw)
    return SimpleNamespace(**base)


def remote(code, updated):
    return {"UpdatedDateUTC": updated, "LineItems": [{"AccountCode": code, "UnitAmount": 10}]}


def test_no_remote_edit_pushes_and_keeps_line_amounts():
    db, x = FakeDB([expense(account_code="300")]), FakeXero(remote("200", "T1"))
    xero_push.push(db, x)
    assert x.updates[0][1]["LineItems"] == [{"AccountCode": "300", "UnitAmount": 10}]
    assert not db.ran("sync_conflicts")


def test_remote_recategorization_flag_policy_preserves_it_and_records_conflict():
    db, x = FakeDB([expense(account_code="300")]), FakeXero(remote("400", "T9"))
    xero_push.push(db, x, policy="flag")
    assert x.updates == []
    assert len(db.ran("INSERT INTO sync_conflicts")) == 1
    assert "400" in db.ran("INSERT INTO sync_conflicts")[0][1][3]
    assert db.ran("sync_status = 'conflict'")


def test_remote_recategorization_theirs_policy_updates_our_ledger():
    db, x = FakeDB([expense(account_code="300")]), FakeXero(remote("400", "T9"))
    xero_push.push(db, x, policy="theirs")
    assert x.updates == []
    assert db.ran("UPDATE expenses SET account_code")[0][1][0] == "400"
    assert len(db.ran("INSERT INTO sync_conflicts")) == 1


def test_remote_recategorization_ours_policy_overwrites_but_records_conflict():
    db, x = FakeDB([expense(account_code="300")]), FakeXero(remote("400", "T9"))
    xero_push.push(db, x, policy="ours")
    assert x.updates[0][1]["LineItems"][0]["AccountCode"] == "300"
    assert len(db.ran("INSERT INTO sync_conflicts")) == 1


def test_unknown_policy_rejected():
    with pytest.raises(ValueError):
        xero_push.push(FakeDB([]), FakeXero({}), policy="whatever")
