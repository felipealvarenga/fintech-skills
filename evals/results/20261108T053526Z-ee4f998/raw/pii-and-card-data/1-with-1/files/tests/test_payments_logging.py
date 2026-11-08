import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import payments_api  # noqa: E402

PAN = "4111111111111111"
CVV = "737"
CPF = "529.982.247-25"
EMAIL = "jane@example.com"
TOKEN = "tok_secret_abc123"

REQUEST = {
    "order_id": "o-1", "amount": 1000, "currency": "BRL", "last4": "1111",
    "card_number": PAN, "cvv": CVV, "cpf": CPF, "email": EMAIL,
    "token": TOKEN, "card": {"number": PAN, "cvv": CVV},
}
RESPONSE = {
    "id": "ch_1", "status": "declined", "decline_code": "insufficient_funds",
    "card_number": PAN, "cvv": CVV, "token": TOKEN, "email": EMAIL,
    "echo": {"number": PAN},
}


class FakeProcessor:
    def charge(self, body):
        return RESPONSE


def _assert_clean(text):
    for secret in (PAN, CVV, CPF, EMAIL, TOKEN):
        assert secret not in text


def test_no_sensitive_data_in_logs(caplog):
    caplog.set_level(logging.DEBUG, logger="payments")
    payments_api.charge(SimpleNamespace(json=REQUEST), FakeProcessor())
    _assert_clean(caplog.text)
    assert "insufficient_funds" in caplog.text  # still useful for declines


def test_no_sensitive_data_in_logs_on_error(caplog):
    class Boom:
        def charge(self, body):
            raise RuntimeError(f"bad card {PAN}")

    caplog.set_level(logging.DEBUG, logger="payments")
    try:
        payments_api.charge(SimpleNamespace(json=REQUEST), Boom())
    except RuntimeError:
        pass
    _assert_clean(caplog.text)
