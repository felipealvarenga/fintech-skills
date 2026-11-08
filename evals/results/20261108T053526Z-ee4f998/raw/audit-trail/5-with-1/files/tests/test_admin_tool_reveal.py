import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from admin_tool import Actor, RevealDenied, customer_page, reveal_cpf  # noqa: E402

CPF = "123.456.789-09"


class MemAudit:
    def __init__(self, fail=False):
        self.events, self.fail = [], fail

    def append(self, event):
        if self.fail:
            raise RuntimeError("audit down")
        self.events.append(event)


def cust():
    return SimpleNamespace(id="c1", name="Ana", cpf=CPF, cards=[SimpleNamespace(last4="4242")])


def args(audit, **kw):
    base = dict(actor=Actor("rep-7"), reason_code="IDENTITY_VERIFICATION",
                reason_text="caller verification", request_id="req-1", audit=audit)
    base.update(kw)
    return base


def test_default_page_is_masked_and_writes_no_event():
    assert customer_page(cust())["cpf"] == "***.456.789-**"


def test_reveal_returns_full_cpf_and_writes_one_event():
    a = MemAudit()
    page = customer_page(cust(), reveal=args(a))
    assert page["cpf"] == CPF
    assert len(a.events) == 1
    e = a.events[0]
    assert (e["action"], e["actor_id"], e["actor_type"], e["request_id"]) == ("cpf.reveal", "rep-7", "user", "req-1")
    assert e["reason_code"] == "IDENTITY_VERIFICATION" and e["object_id"] == "c1"


def test_event_never_contains_full_cpf():
    a = MemAudit()
    reveal_cpf(cust(), **args(a))
    assert "123.456.789-09" not in repr(a.events) and "12345678909" not in repr(a.events)


@pytest.mark.parametrize("kw", [dict(reason_code="BECAUSE"), dict(reason_text=" "), dict(request_id="")])
def test_missing_reason_denied_and_no_event(kw):
    a = MemAudit()
    with pytest.raises(RevealDenied):
        reveal_cpf(cust(), **args(a, **kw))
    assert a.events == []


def test_failed_audit_write_reveals_nothing():
    with pytest.raises(RuntimeError):
        reveal_cpf(cust(), **args(MemAudit(fail=True)))
