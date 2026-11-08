import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from token_refresh import call_with_refresh


class Conn:
    def __init__(self):
        self.access_token = "old-access"
        self.refresh_token = "old-refresh"
        self.saved = None

    def access_token_expired(self):
        return True

    def save(self):
        self.saved = (self.access_token, self.refresh_token)


class Api:
    def __init__(self, fail_call=False):
        self.fail_call = fail_call

    def refresh(self, refresh_token):
        assert refresh_token == "old-refresh"
        return {"access_token": "new-access", "refresh_token": "new-refresh",
                "x_refresh_token_expires_in": 8640000}

    def call(self, request, access_token):
        if self.fail_call:
            raise TimeoutError("boom")
        return "ok"


def test_new_refresh_token_persisted_even_if_call_fails():
    conn = Conn()
    with pytest.raises(TimeoutError):
        call_with_refresh(conn, Api(fail_call=True), "req")
    assert conn.saved == ("new-access", "new-refresh")


def test_success_saves_tokens_and_expiry():
    conn = Conn()
    assert call_with_refresh(conn, Api(), "req") == "ok"
    assert conn.saved == ("new-access", "new-refresh")
    assert conn.refresh_token_expires_at > 0
