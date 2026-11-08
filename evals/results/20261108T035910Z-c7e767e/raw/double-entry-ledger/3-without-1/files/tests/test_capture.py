import pytest

from payments.capture import capture_entries


def balance(entries, account):
    return sum(e.debit - e.credit for e in entries if e.account == account)


def test_100_capture_2_90_fee_5_kept():
    entries = capture_entries(amount=10000, processor_fee=290, our_share=500)

    assert balance(entries, "processor_receivable") == 9710
    assert balance(entries, "processor_fee_expense") == 290
    assert balance(entries, "merchant_payable") == -9500
    assert balance(entries, "platform_revenue") == -500
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries) == 10000
    # Net margin after processor cost: $5.00 - $2.90 = $2.10
    assert -balance(entries, "platform_revenue") - balance(entries, "processor_fee_expense") == 210


def test_share_cannot_exceed_amount():
    with pytest.raises(ValueError):
        capture_entries(amount=100, processor_fee=0, our_share=200)
