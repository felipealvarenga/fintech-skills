import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import refund_job
from refund_job import ProcessorDeclined


class R:
    def __init__(self, id, status="approved"):
        self.id, self.payment_id, self.amount, self.status = id, "pay1", 100, status


class FakeDB:
    def __init__(self, rows):
        self.rows = {r.id: r for r in rows}

    def query(self, sql):
        status = "pending" if "'pending'" in sql else "approved"
        return [r for r in list(self.rows.values()) if r.status == status]

    def execute(self, sql, params):
        rid = params[-1]
        r = self.rows[rid]
        if "'pending' WHERE id = %s AND status = 'approved'" in sql:
            if r.status != "approved":
                return 0
            r.status = "pending"
            return 1
        new = "sent" if "'sent'" in sql else "failed"
        if r.status != "pending":
            return 0
        r.status = new
        return 1


class FakeProcessor:
    """Dedupes by idempotency key like a real processor; can time out on command."""

    def __init__(self):
        self.done, self.calls, self.timeout_next, self.decline = {}, 0, False, False

    def refund(self, payment_id, amount, idempotency_key):
        self.calls += 1
        if self.decline:
            raise ProcessorDeclined()
        self.done.setdefault(idempotency_key, object())
        if self.timeout_next:
            self.timeout_next = False
            raise TimeoutError()
        return type("Res", (), {"id": idempotency_key})()


def test_restart_does_not_double_refund():
    db, p = FakeDB([R(1)]), FakeProcessor()
    refund_job.run(db, p)
    refund_job.run(db, p)  # restarted worker
    assert p.calls == 1 and db.rows[1].status == "sent"


def test_already_claimed_row_not_sent_by_second_worker():
    db, p = FakeDB([R(1, "pending")]), FakeProcessor()
    refund_job.run(db, p)
    assert p.calls == 0


def test_timeout_stays_pending_then_reconciler_uses_same_key():
    db, p = FakeDB([R(1)]), FakeProcessor()
    p.timeout_next = True
    refund_job.run(db, p)
    assert db.rows[1].status == "pending"
    refund_job.run(db, p)
    assert p.calls == 1  # run() does not resend pending rows
    refund_job.reconcile(db, p)
    assert db.rows[1].status == "sent"
    assert len(p.done) == 1  # one refund at the processor


def test_confirmed_decline_marks_failed():
    db, p = FakeDB([R(1)]), FakeProcessor()
    p.decline = True
    refund_job.run(db, p)
    assert db.rows[1].status == "failed"
