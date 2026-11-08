import pytest

from src.money_module import allocate, apply_rate, to_minor


@pytest.mark.parametrize(
    "amount,currency,expected",
    [
        ("1.23", "USD", 123),
        ("1.23", "BRL", 123),
        ("100", "JPY", 100),
        ("1.234", "BHD", 1234),
        ("0", "USD", 0),
        ("-1.23", "USD", -123),
    ],
)
def test_to_minor(amount, currency, expected):
    assert to_minor(amount, currency) == expected


def test_to_minor_unknown_currency():
    with pytest.raises(KeyError):
        to_minor("1", "XXX")


@pytest.mark.parametrize(
    "amount,ratios,expected",
    [
        (100, [1, 1, 1], [34, 33, 33]),
        (5, [1, 1], [3, 2]),
        (10, [3, 7], [3, 7]),
        (0, [1, 2], [0, 0]),
        (100, [1], [100]),
    ],
)
def test_allocate(amount, ratios, expected):
    result = allocate(amount, ratios)
    assert result == expected
    assert sum(result) == amount


def test_allocate_largest_remainder_gets_extra():
    # 10*[1,2,2]/5 = 2,4,4 exact; 7*[1,1,5]/7 exact; use uneven remainders
    result = allocate(10, [1, 1, 2])  # 2.5, 2.5, 5 -> 2,2,5 rem 1
    assert sum(result) == 10
    assert result == [3, 2, 5]


@pytest.mark.parametrize(
    "amount,rate,expected",
    [
        (100, "1.005", 100),  # 100.5 -> even
        (101, "1.005", 102),  # 101.505 -> up
        (1, "0.5", 0),  # 0.5 -> 0
        (3, "0.5", 2),  # 1.5 -> 2
        (5, "0.5", 2),  # 2.5 -> 2
        (100, "2", 200),
        (-5, "0.5", -2),
    ],
)
def test_apply_rate(amount, rate, expected):
    assert apply_rate(amount, rate) == expected
