"""Unrun (no shell was available when written). Run: pytest tests -q from the repo root."""
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import billing, boleto, charges, documents, models, settlement, wallet  # noqa: E402


def test_split_sums_exactly():
    parts = billing.split_invoice(100, [Decimal(1)] * 3)
    assert sum(parts) == 100 and sorted(parts) == [33, 33, 34]


@pytest.mark.parametrize("s,c", [("19.99", 1999), ("0.29", 29), ("1.005", 100), ("10", 1000)])
def test_to_cents(s, c):
    assert billing.to_cents(s) == c


def test_to_cents_rejects_garbage():
    with pytest.raises(ValueError):
        billing.to_cents("nan")


def test_same_order_same_idempotency_key():
    o = SimpleNamespace(id="42", amount_cents=500)
    with mock.patch.object(charges.stripe.PaymentIntent, "create") as c:
        charges.create_charge(o)
        charges.create_charge(o)
    keys = {call.kwargs["idempotency_key"] for call in c.call_args_list}
    assert len(keys) == 1


def test_fee_bps():
    assert charges.platform_fee_cents(10_000) == 350
    assert charges.platform_fee_cents(1) == 0


def test_wallet_uses_insert_not_update():
    db = mock.MagicMock()
    db.execute.return_value.fetchone.return_value = (1000,)
    wallet.pay(db, "u1", 300, "ref-1")
    sqls = [c.args[0] for c in db.execute.call_args_list]
    assert not any("UPDATE" in s for s in sqls) and any("INSERT" in s for s in sqls)


def test_wallet_insufficient():
    db = mock.MagicMock()
    db.execute.return_value.fetchone.return_value = (100,)
    with pytest.raises(wallet.InsufficientFunds):
        wallet.pay(db, "u1", 300, "ref-2")


def test_card_has_no_pan_or_cvv():
    fields = models.Card.__dataclass_fields__
    assert "cvv" not in fields and "card_number" not in fields


def test_cnpj():
    assert documents.validate_cnpj("11.222.333/0001-81")
    assert not documents.validate_cnpj("11222333000180")
    assert not documents.validate_cnpj("00000000000000")
    assert not documents.validate_cnpj("1122233300018")


def test_boleto_stays_pending_until_confirmed():
    order = SimpleNamespace(status="new")
    boleto.generate_boleto(order, mock.Mock())
    assert order.status == "pending"
    boleto.confirm_boleto_paid(order, "paid")
    assert order.status == "paid"


def test_settlement_skips_weekend_and_holiday():
    fri = lambda: datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    assert settlement.settlement_date(fri) == date(2026, 11, 9)
    assert settlement.settlement_date(fri, holidays=[date(2026, 11, 9)]) == date(2026, 11, 10)
