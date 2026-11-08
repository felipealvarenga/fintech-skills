import json

import pytest

from src.customer_deletion import delete_customer
from src.customer_model import Customer, PaymentMethod


class Customers:
    def __init__(self, rows): self.rows = {c.id: c for c in rows}
    def get(self, cid): return self.rows.get(cid)
    def delete(self, cid): self.rows.pop(cid, None)


class Methods:
    def __init__(self, rows): self.rows = list(rows)
    def list_for_customer(self, cid): return [m for m in self.rows if m.customer_id == cid]
    def delete_for_customer(self, cid):
        n = len(self.list_for_customer(cid))
        self.rows = [m for m in self.rows if m.customer_id != cid]
        return n


class Index:
    def __init__(self, ids): self.ids = set(ids)
    def remove_customer(self, cid): self.ids.discard(cid)


class Processor:
    def __init__(self, fail=False): self.deleted, self.fail = [], fail
    def delete_token(self, t):
        if self.fail: raise RuntimeError("processor down")
        self.deleted.append(t)


class Audit:
    def __init__(self): self.events = []
    def record(self, e): self.events.append(e)


def setup():
    cs = [Customer("c1", "Ana Silva", "ana@example.com", "123.456.789-09"),
          Customer("c2", "Bob", "bob@example.com", "987.654.321-00")]
    ms = [PaymentMethod("c1", "visa", "4242", "tok_1"),
          PaymentMethod("c2", "visa", "1111", "tok_2")]
    return Customers(cs), Methods(ms), Index(["c1", "c2"]), Processor(), Audit()


def run(c, m, i, p, a):
    return delete_customer("c1", customers=c, payment_methods=m, index=i, processor=p, audit=a)


def test_rows_index_and_tokens_removed_others_untouched():
    c, m, i, p, a = setup()
    r = run(c, m, i, p, a)
    assert "c1" not in c.rows and "c2" in c.rows
    assert [x.customer_id for x in m.rows] == ["c2"]
    assert i.ids == {"c2"}
    assert p.deleted == ["tok_1"]
    assert r.payment_methods_deleted == 1


def test_audit_has_no_personal_data():
    c, m, i, p, a = setup()
    run(c, m, i, p, a)
    blob = json.dumps(a.events)
    for s in ("c1", "Ana", "ana@example.com", "123.456.789-09", "tok_1", "4242"):
        assert s not in blob


def test_processor_failure_keeps_local_rows_for_retry():
    c, m, i, p, a = setup()
    p.fail = True
    with pytest.raises(RuntimeError):
        run(c, m, i, p, a)
    assert "c1" in c.rows and len(m.list_for_customer("c1")) == 1
    p.fail = False
    run(c, m, i, p, a)
    assert "c1" not in c.rows


def test_idempotent():
    c, m, i, p, a = setup()
    run(c, m, i, p, a)
    r = run(c, m, i, p, a)
    assert not r.customer_deleted and r.payment_methods_deleted == 0
