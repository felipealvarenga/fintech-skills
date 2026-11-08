import pytest

from payments import CardCapture, dollars, example


def test_example_amounts():
    c = example()
    assert c.gross_cents == 10_000
    assert c.settled_cents == 9_710
    assert c.our_share_cents == 500
    assert c.merchant_payable_cents == 9_210


def test_funds_fully_allocated():
    c = example()
    assert c.our_share_cents + c.merchant_payable_cents + c.processor_fee_cents == c.gross_cents


def test_journal_balances():
    lines = example().journal()
    assert sum(d for _, d, _ in lines) == sum(cr for _, _, cr in lines)


def test_dollars_format():
    assert dollars(9_210) == "$92.10"
    assert dollars(500) == "$5.00"


def test_rejects_floats():
    with pytest.raises(TypeError):
        CardCapture(100.0, 290, 500)


def test_rejects_fee_above_gross():
    with pytest.raises(ValueError):
        CardCapture(100, 290, 0)


def test_rejects_share_above_settled():
    with pytest.raises(ValueError):
        CardCapture(10_000, 290, 9_800)
