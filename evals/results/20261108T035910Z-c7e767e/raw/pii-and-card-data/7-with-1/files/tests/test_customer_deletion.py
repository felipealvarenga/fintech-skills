import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from customer_model import Customer, PaymentMethod, delete_customer_data


class FakeStore:
    def __init__(self):
        self.customers = {"c1": Customer("c1", "Ana", "ana@example.com", "000.000.000-00"),
                          "c2": Customer("c2", "Bia", "bia@example.com", "111.111.111-11")}
        self.pms = [PaymentMethod("c1", "visa", "4242", "tok_1"),
                    PaymentMethod("c2", "visa", "1111", "tok_2")]

    def delete_customer(self, cid):
        return 1 if self.customers.pop(cid, None) else 0

    def list_payment_methods(self, cid):
        return [p for p in self.pms if p.customer_id == cid]

    def delete_payment_methods(self, cid):
        n = len(self.list_payment_methods(cid))
        self.pms = [p for p in self.pms if p.customer_id != cid]
        return n


class FakeIndex:
    def __init__(self):
        self.ids = {"c1", "c2"}

    def delete_customer(self, cid):
        self.ids.discard(cid)


class FakeProcessor:
    def __init__(self):
        self.revoked = []

    def delete_token(self, token):
        self.revoked.append(token)


def test_deletes_only_target_customer_everywhere():
    s, i, p = FakeStore(), FakeIndex(), FakeProcessor()
    r = delete_customer_data("c1", s, i, p)
    assert "c1" not in s.customers and "c2" in s.customers
    assert [x.customer_id for x in s.pms] == ["c2"]
    assert i.ids == {"c2"}
    assert p.revoked == ["tok_1"]
    assert (r.customers_deleted, r.payment_methods_deleted, r.tokens_revoked) == (1, 1, 1)


def test_idempotent_rerun():
    s, i, p = FakeStore(), FakeIndex(), FakeProcessor()
    delete_customer_data("c1", s, i, p)
    r = delete_customer_data("c1", s, i, p)
    assert r.customers_deleted == 0 and r.tokens_revoked == 0


def test_receipt_has_no_pii():
    s, i, p = FakeStore(), FakeIndex(), FakeProcessor()
    r = delete_customer_data("c1", s, i, p)
    text = repr(r)
    for pii in ("Ana", "ana@example.com", "000.000.000-00", "tok_1", "4242"):
        assert pii not in text
