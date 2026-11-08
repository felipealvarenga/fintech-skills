import hashlib
import hmac
import logging
from types import SimpleNamespace

import pytest

from src import cpf as cpf_lib
from src.admin_view import customer_detail
from src.signup import signup

VALID = "529.982.247-25"  # synthetic, valid check digits


class FakeVault:
    def encrypt(self, s):
        return b"enc:" + bytes(reversed(s.encode()))

    def blind_index(self, s):
        return hmac.new(b"test-key", s.encode(), hashlib.sha256).hexdigest()


class FakeDB:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def form(cpf=VALID):
    return {"name": "Ana", "email": "ana@example.com", "cpf": cpf}


def test_valid_and_invalid_cpf():
    assert cpf_lib.is_valid(VALID)
    assert not cpf_lib.is_valid("111.111.111-11")
    assert not cpf_lib.is_valid("529.982.247-26")
    assert not cpf_lib.is_valid("123")


def test_signup_stores_no_plaintext_cpf():
    db = FakeDB()
    signup(form(), db, FakeVault())
    _, params = db.calls[0]
    assert all("52998224725" not in str(p) for p in params)
    assert params[4] == "***.***.***-25"


def test_signup_rejects_invalid_cpf():
    with pytest.raises(ValueError) as e:
        signup(form("111.111.111-11"), FakeDB(), FakeVault())
    assert "111" not in str(e.value)


def test_signup_logs_no_cpf(caplog):
    with caplog.at_level(logging.DEBUG):
        signup(form(), FakeDB(), FakeVault())
    assert "52998224725" not in caplog.text and "529.982" not in caplog.text


def test_admin_shows_masked_cpf_only():
    c = SimpleNamespace(name="Ana", email="a@x.com", cpf_masked="***.***.***-25")
    out = customer_detail(c)
    assert out["cpf"] == "***.***.***-25"
    assert "52998224725" not in str(out)
