"""Test vectors for brazil-payment-rails.

Run against the reference: `pytest skills/brazil-payment-rails`.
Run against your module:   `BRAZIL_SOLUTION=/path/to/brazil.py pytest skills/brazil-payment-rails`.

The module under test must expose validate_cpf, mask_cpf, validate_cnpj, cnpj_check_digits,
normalize_cnpj, format_cnpj, mod10, mod11_barcode, build_barcode, validate_barcode,
typeable_line, barcode_from_typeable_line, factor_from_due_date and due_date_from_factor.
All identifiers below are synthetic or the regulator's published examples.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("BRAZIL_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("brazil_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


# CPF ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cpf,valid", [
    ("529.982.247-25", True),
    ("52998224725", True),
    ("529.982.247-26", False),
    ("111.111.111-11", False),
    ("000.000.000-00", False),
    ("1234567890", False),
    ("529.982.247-2A", False),
])
def test_validate_cpf(cpf, valid):
    assert m.validate_cpf(cpf) is valid


def test_mask_cpf_shows_middle_digits_only():
    assert m.mask_cpf("529.982.247-25") == "***.982.247-**"


# CNPJ ------------------------------------------------------------------------------------------

def test_cnpj_official_alphanumeric_example():
    # Receita Federal's published example: 12.ABC.345/01DE-35
    assert m.cnpj_check_digits("12ABC34501DE") == "35"
    assert m.validate_cnpj("12.ABC.345/01DE-35") is True
    assert m.validate_cnpj("12.ABC.345/01DE-36") is False


@pytest.mark.parametrize("cnpj,valid", [
    ("11.222.333/0001-81", True),
    ("11222333000181", True),
    ("11.222.333/0001-82", False),
    ("00.000.000/0000-00", False),
    ("11.222.333/0001-8", False),
    ("12.abc.345/01de-35", True),   # lower case input is normalized
    ("12.ABC.345/01DE-3A", False),  # check digits are always numeric
])
def test_validate_cnpj(cnpj, valid):
    assert m.validate_cnpj(cnpj) is valid


def test_cnpj_normalize_and_format():
    assert m.normalize_cnpj("12.abc.345/01de-35") == "12ABC34501DE35"
    assert m.format_cnpj("12ABC34501DE35") == "12.ABC.345/01DE-35"
    assert m.format_cnpj("11222333000181") == "11.222.333/0001-81"
    with pytest.raises(Exception):
        m.normalize_cnpj("11.222.333/0001-82")


def test_cnpj_letters_are_not_stripped():
    # stripping letters would turn a valid alphanumeric CNPJ into a different, shorter string
    assert m.validate_cnpj("1234501DE35") is False


# Boleto check digits -----------------------------------------------------------------------------

@pytest.mark.parametrize("digits,dv", [
    ("1", 8), ("9", 1), ("0", 0), ("12345", 5),
    ("001905009", 5), ("4014481606", 9), ("0680935031", 4),  # the three fields of the published sample line
])
def test_mod10(digits, dv):
    assert m.mod10(digits) == dv


def test_mod11_barcode_edge_rule():
    assert m.mod11_barcode("0" * 43) == 1  # remainder 0 -> 11 -> 1
    with pytest.raises(Exception):
        m.mod11_barcode("0" * 44)


SAMPLE_LINE = "00190500954014481606906809350314337370000000100"  # widely published Banco do Brasil sample, R$ 1,00


def test_published_sample_line_validates_and_round_trips():
    barcode = m.barcode_from_typeable_line(SAMPLE_LINE)
    assert barcode == "00193373700000001000500940144816060680935031"
    assert m.validate_barcode(barcode) and barcode[4] == "3"
    assert m.typeable_line(barcode) == SAMPLE_LINE
    assert int(barcode[9:19]) == 100
    assert m.due_date_from_factor(int(barcode[5:9]), date(2008, 1, 1)) == date(2007, 12, 31)


def _sample_barcode():
    factor = m.factor_from_due_date(date(2026, 3, 10))
    return m.build_barcode("001", factor, 123456, "1234567890123456789012345")


def test_barcode_round_trip_through_typeable_line():
    barcode = _sample_barcode()
    assert len(barcode) == 44 and m.validate_barcode(barcode)
    line = m.typeable_line(barcode)
    assert len(line) == 47 and line.isdigit()
    assert m.barcode_from_typeable_line(line) == barcode
    # the five fields: 10 + 11 + 11 + 1 + 14
    assert line[32] == barcode[4]
    assert line[33:47] == barcode[5:19]


def test_tampered_line_is_rejected():
    line = m.typeable_line(_sample_barcode())
    # every digit inside the three mod-10 fields and the barcode check digit itself
    for pos in list(range(0, 32)) + [32]:
        bad = line[:pos] + str((int(line[pos]) + 1) % 10) + line[pos + 1:]
        with pytest.raises(Exception):
            m.barcode_from_typeable_line(bad)


def test_mod11_general_digit_does_not_catch_every_change_in_the_fifth_field():
    # 0, 10 and 11 all map to 1, so a single-digit change in the factor or amount can slip past
    # the barcode digit. The typeable line's mod-10 field digits are the real protection, and
    # the amount must be checked against the charge record, never trusted from the line alone.
    line = m.typeable_line(_sample_barcode())
    slipped = 0
    for pos in range(33, 47):
        for delta in range(1, 10):
            bad = line[:pos] + str((int(line[pos]) + delta) % 10) + line[pos + 1:]
            try:
                m.barcode_from_typeable_line(bad)
                slipped += 1
            except Exception:
                pass
    assert 0 < slipped < 14 * 9


def test_barcode_encodes_amount_and_factor():
    barcode = _sample_barcode()
    assert barcode[0:3] == "001" and barcode[3] == "9"
    assert int(barcode[5:9]) == m.factor_from_due_date(date(2026, 3, 10))
    assert int(barcode[9:19]) == 123456


# Due-date factor ---------------------------------------------------------------------------------

@pytest.mark.parametrize("due,factor", [
    (date(2000, 7, 3), 1000),
    (date(2025, 2, 21), 9999),
    (date(2025, 2, 22), 1000),   # the reset
    (date(2025, 3, 1), 1007),
    (date(2026, 3, 10), 1381),
])
def test_factor_from_due_date(due, factor):
    assert m.factor_from_due_date(due) == factor


def test_factor_out_of_range():
    with pytest.raises(Exception):
        m.factor_from_due_date(date(1999, 1, 1))


@pytest.mark.parametrize("factor,reference,due", [
    (1007, date(2025, 1, 10), date(2025, 3, 1)),   # issued before the reset, due after it
    (9800, date(2024, 6, 1), date(2024, 8, 6)),
    (1000, date(2025, 2, 25), date(2025, 2, 22)),
    (1000, date(2000, 7, 1), date(2000, 7, 3)),
])
def test_due_date_from_factor_picks_the_cycle_closest_to_the_reference(factor, reference, due):
    assert m.due_date_from_factor(factor, reference) == due


def test_factor_round_trip():
    for d in (date(2024, 12, 31), date(2025, 2, 21), date(2025, 2, 22), date(2030, 1, 1)):
        assert m.due_date_from_factor(m.factor_from_due_date(d), d) == d
