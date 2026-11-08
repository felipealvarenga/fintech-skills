from payments import PaymentService, FakeProcessor, IdempotencyStore


def test_charge_once():
    svc = PaymentService(IdempotencyStore(), FakeProcessor())
    assert svc.charge("t1", "k1", {"amount": 1000})["status"] == "succeeded"
