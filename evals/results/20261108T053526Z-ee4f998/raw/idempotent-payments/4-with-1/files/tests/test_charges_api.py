"""Unrun: written without a shell. Run with `pytest tests/` (needs `stripe` installed)."""
import sys
import threading
import types
from pathlib import Path

import pytest
import stripe

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import charges_api as api  # noqa: E402


class FakeStripe:
    """Dedupes by idempotency key like Stripe; can time out or fail on command."""
    def __init__(self):
        self.created, self.by_key, self.calls, self.script = [], {}, 0, []
        self.lock = threading.Lock()

    def create(self, **kw):
        with self.lock:
            self.calls += 1
            action = self.script.pop(0) if self.script else "ok"
            if action == "timeout_after_success":
                self._make(kw)
                raise stripe.error.APIConnectionError("timeout")
            if action == "503":
                raise stripe.error.APIError("503")
            if action == "400":
                raise stripe.error.InvalidRequestError("bad", "amount")
            return self._make(kw)

    def _make(self, kw):
        key = kw["idempotency_key"]
        if key not in self.by_key:
            self.by_key[key] = types.SimpleNamespace(id=f"pi_{len(self.by_key)}", status="succeeded", kw=kw)
            self.created.append(key)
        return self.by_key[key]


@pytest.fixture
def env(monkeypatch, tmp_path):
    fake = FakeStripe()
    monkeypatch.setattr(stripe, "PaymentIntent", types.SimpleNamespace(
        create=fake.create,
        search=lambda query: types.SimpleNamespace(
            data=[v for v in fake.by_key.values() if v.kw["metadata"]["charge_id"] in query])))
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    db = api.get_db(str(tmp_path / "c.db"))
    return fake, db


def make(db, amount=1000):
    req = types.SimpleNamespace(json={"amount": amount, "currency": "usd"})
    body, code = api.create_charge(req, db)
    assert code == 201
    return body["id"]


def test_create_moves_no_money(env):
    fake, db = env
    make(db)
    assert fake.calls == 0


def test_confirm_twice_one_charge_same_response(env):
    fake, db = env
    cid = make(db)
    r1, r2 = api.confirm_charge(cid, db), api.confirm_charge(cid, db)
    assert r1 == r2 and len(fake.created) == 1


def test_timeout_then_retry_same_url_one_charge(env):
    fake, db = env
    fake.script = ["timeout_after_success"] * api.POLICY.max_attempts
    cid = make(db)
    body, code = api.confirm_charge(cid, db)
    assert (code, body["status"]) == (202, "pending")
    body, code = api.confirm_charge(cid, db)
    assert code == 200 and body["status"] == "succeeded" and len(fake.created) == 1


def test_timeout_client_disappears_reconciler_resolves(env):
    fake, db = env
    fake.script = ["timeout_after_success"] * api.POLICY.max_attempts
    cid = make(db)
    api.confirm_charge(cid, db)
    api.reconcile_pending(db, older_than=-1)
    assert db.execute("SELECT status FROM charges WHERE id=?", (cid,)).fetchone()[0] == "succeeded"
    assert len(fake.created) == 1


def test_concurrent_confirms_one_charge(env):
    fake, db = env
    cid = make(db)
    results = []
    ts = [threading.Thread(target=lambda: results.append(api.confirm_charge(cid, api.get_db(db.execute("PRAGMA database_list").fetchone()[2])))) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(fake.created) == 1


def test_400_not_retried_and_marks_failed(env):
    fake, db = env
    fake.script = ["400"]
    cid = make(db)
    body, code = api.confirm_charge(cid, db)
    assert code == 400 and fake.calls == 1 and body["status"] == "failed"


def test_503_retried_up_to_limit_then_pending(env):
    fake, db = env
    fake.script = ["503"] * 10
    cid = make(db)
    body, code = api.confirm_charge(cid, db)
    assert fake.calls == api.POLICY.max_attempts and (code, body["status"]) == (202, "pending")


def test_503_then_success(env):
    fake, db = env
    fake.script = ["503"]
    cid = make(db)
    assert api.confirm_charge(cid, db)[1] == 200 and fake.calls == 2


def test_confirm_unknown_id_404(env):
    _, db = env
    assert api.confirm_charge("chg_nope", db)[1] == 404
