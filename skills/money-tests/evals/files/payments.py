"""Payment service under test (interface only)."""


class IdempotencyStore: ...


class FakeProcessor:
    def __init__(self, script=None): ...


class PaymentService:
    def __init__(self, store, processor): ...

    def charge(self, tenant, key, payload): ...
