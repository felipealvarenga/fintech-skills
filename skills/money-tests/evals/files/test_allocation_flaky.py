import random
from money_module import allocate


def test_allocation_property():
    amount = random.randint(-10**6, 10**6)
    ratios = [random.randint(0, 9) for _ in range(random.randint(1, 5))]
    parts = allocate(amount, ratios)
    assert sum(parts) == amount
