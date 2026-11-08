import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import payments_api  # noqa: E402

PAN = "4111111111111111"
CVV = "123"
CPF = "529.982.247-25"
TOKEN = "tok_secret_abc"
EMAIL = "jane@example.com"


class Processor:
    def charge(self, body):
        return {"id": "ch_1", "status": "declined", "decline_code": "insufficient_funds",
                "message": f"card {PAN} for {EMAIL} declined", "card": {"number": PAN}}


def test_no_sensitive_data_in_logs(caplog):
    req = SimpleNamespace(json={
        "order_id": "o1", "amount": 1000, "currency": "BRL", "brand": "visa", "last4": "1111",
        "card_number": PAN, "cvv": CVV, "cpf": CPF, "token": TOKEN, "email": EMAIL,
        "password": "hunter2",
    })
    with caplog.at_level(logging.DEBUG, logger="payments"):
        payments_api.charge(req, Processor())
    text = caplog.text
    for secret in (PAN, CVV, CPF, TOKEN, EMAIL, "hunter2"):
        assert secret not in text
    assert "insufficient_funds" in text and "o1" in text


def test_full_pan_in_last4_is_blocked(caplog):
    req = SimpleNamespace(json={"last4": PAN})
    with caplog.at_level(logging.DEBUG, logger="payments"):
        payments_api.charge(req, Processor())
    assert PAN not in caplog.text
