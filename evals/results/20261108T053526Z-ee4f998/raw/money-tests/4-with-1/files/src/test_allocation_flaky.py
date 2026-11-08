import random

import pytest

from money_module import allocate

SEED = 20261108
CASES = 500


def test_allocation_property_preserves_sum():
    rng = random.Random(SEED)
    for _ in range(CASES):
        amount = rng.randint(-10**6, 10**6)
        ratios = [rng.randint(0, 9) for _ in range(rng.randint(1, 5))]
        if sum(ratios) == 0:
            ratios[rng.randrange(len(ratios))] = rng.randint(1, 9)
        parts = allocate(amount, ratios)
        assert len(parts) == len(ratios)
        assert sum(parts) == amount
        # zero ratio gets nothing; shares stay within one minor unit of exact
        for part, r in zip(parts, ratios):
            if r == 0:
                assert part == 0
            assert abs(part - amount * r / sum(ratios)) < 1


@pytest.mark.parametrize(
    "amount, ratios, expected",
    [
        (100, [1, 1, 1], [34, 33, 33]),
        (100, [1, 2], [33, 67]),
        (5, [1, 1], [3, 2]),
        (0, [1, 1], [0, 0]),
        (1, [1, 1, 1], [1, 0, 0]),
        (100, [0, 1], [0, 100]),
    ],
)
def test_allocation_vectors(amount, ratios, expected):
    # Vectors need human review before merge (rule 2).
    assert allocate(amount, ratios) == expected


@pytest.mark.parametrize("ratios", [[0], [0, 0, 0], []])
def test_allocation_rejects_no_positive_ratio(ratios):
    with pytest.raises(ValueError):
        allocate(100, ratios)
