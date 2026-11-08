import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cnpj import normalize_cnpj, validate_cnpj


def test_valid_numeric():
    assert validate_cnpj("11222333000181")


def test_invalid_check_digit_numeric():
    assert not validate_cnpj("11222333000182")
    assert not validate_cnpj("12345678901234")


def test_alphanumeric_accepted():
    assert validate_cnpj("12ABC34501DE35")


def test_alphanumeric_bad_check_digit():
    assert not validate_cnpj("12ABC34501DE36")


def test_formatted_input_normalized():
    assert validate_cnpj("12.ABC.345/01DE-35")
    assert validate_cnpj("11.222.333/0001-81")
    assert normalize_cnpj("12.abc.345/01de-35") == "12ABC34501DE35"


def test_lowercase_accepted():
    assert validate_cnpj("12abc34501de35")


def test_letters_not_allowed_in_check_digits():
    assert not validate_cnpj("12ABC34501DEAB")


def test_wrong_length_and_repeated():
    assert not validate_cnpj("1122233300018")
    assert not validate_cnpj("00000000000000")
    assert not validate_cnpj("")
