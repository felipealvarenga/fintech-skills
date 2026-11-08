from payments import charge, refund


def test_charge_works():
    result = charge(1000, "USD")
    assert result is not None


def test_refund_works():
    result = refund("pay_1", 500)
    assert result
