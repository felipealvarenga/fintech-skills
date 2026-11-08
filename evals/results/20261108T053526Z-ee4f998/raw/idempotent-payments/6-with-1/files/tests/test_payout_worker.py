import os
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import payout_worker  # noqa: E402


class FakeDB:
    """In-memory stand-in; the claim is atomic under a lock like SKIP LOCKED."""

    def __init__(self, n=1):
        self.jobs = {i: "queued" for i in range(1, n + 1)}
        self.lock = threading.Lock()

    def query_one(self, sql, params=()):
        with self.lock:
            for i, s in self.jobs.items():
                if s == "queued":
                    self.jobs[i] = "sending"
                    return SimpleNamespace(id=i)
        return None

    def execute(self, sql, params=()):
        with self.lock:
            (i,) = params
            if "'sent'" in sql and self.jobs[i] == "sending":
                self.jobs[i] = "sent"
            elif "'failed'" in sql and self.jobs[i] == "sending":
                self.jobs[i] = "failed"


class FakeClient:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def send_payout(self, job, idempotency_key):
        self.calls.append((job.id, idempotency_key))
        if self.exc:
            raise self.exc


def test_two_concurrent_workers_send_once():
    db, client = FakeDB(1), FakeClient()
    ts = [threading.Thread(target=payout_worker.process, args=(db, client)) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert client.calls == [(1, "payout-1")]
    assert db.jobs[1] == "sent"


def test_timeout_leaves_job_sending_not_requeued():
    db, client = FakeDB(1), FakeClient(exc=TimeoutError())
    try:
        payout_worker.process(db, client)
    except TimeoutError:
        pass
    assert db.jobs[1] == "sending"
    payout_worker.process(db, client)  # next poll must not resend
    assert len(client.calls) == 1


def test_definite_failure_marks_failed():
    db, client = FakeDB(1), FakeClient(exc=payout_worker.DefiniteFailure())
    try:
        payout_worker.process(db, client)
    except payout_worker.DefiniteFailure:
        pass
    assert db.jobs[1] == "failed"
