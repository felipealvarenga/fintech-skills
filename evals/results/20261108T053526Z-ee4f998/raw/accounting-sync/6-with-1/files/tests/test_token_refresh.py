import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from token_refresh import call_with_refresh  # noqa: E402


class Conn:
    def __init__(self):
        self.access_token = "old_a"
        self.refresh_token = "old_r"
        self.refresh_token_expires_at = None
        self.saved = None

    def access_token_expired(self):
        return True

    def save(self):
        self.saved = (self.access_token, self.refresh_token)


class Api:
    def __init__(self, fail=False):
        self.fail = fail

    def refresh(self, rt):
        assert rt == "old_r"
        return {"access_token": "new_a", "refresh_token": "new_r",
                "x_refresh_token_expires_in": 8640000}

    def call(self, request, token):
        if self.fail:
            raise RuntimeError("boom")
        return "ok"


def test_new_refresh_token_persisted_even_if_call_fails():
    conn = Conn()
    with pytest.raises(RuntimeError):
        call_with_refresh(conn, Api(fail=True), {})
    assert conn.saved == ("new_a", "new_r")


def test_success_saves_token_and_expiry():
    conn = Conn()
    assert call_with_refresh(conn, Api(), {}) == "ok"
    assert conn.saved == ("new_a", "new_r")
    assert conn.refresh_token_expires_at is not None
