"""Reference implementation for the brazil-payment-rails vectors.

CPF and CNPJ check digits (CNPJ including the alphanumeric format issued from July 2026),
boleto barcode and typeable line (linha digitavel) check digits, and the due-date factor with
its 2025-02-22 reset. Synthetic values only.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

CPF_RE = re.compile(r"\d{11}")
CNPJ_RE = re.compile(r"[0-9A-Z]{12}[0-9]{2}")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _alnum(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()


# --- CPF ---------------------------------------------------------------------------------------

def validate_cpf(cpf: str) -> bool:
    d = _digits(cpf)
    if not CPF_RE.fullmatch(d) or len(set(d)) == 1:
        return False
    nums = [int(c) for c in d]
    for n in (9, 10):
        total = sum(nums[i] * (n + 1 - i) for i in range(n))
        r = total % 11
        dv = 0 if r < 2 else 11 - r
        if dv != nums[n]:
            return False
    return True


def mask_cpf(cpf: str) -> str:
    d = _digits(cpf)
    if len(d) != 11:
        raise ValueError("CPF needs 11 digits")
    return f"***.{d[3:6]}.{d[6:9]}-**"


# --- CNPJ (numeric and alphanumeric) ------------------------------------------------------------

_W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_W2 = [6] + _W1


def _cnpj_value(ch: str) -> int:
    """Receita Federal rule: the character's ASCII code minus 48 (digits 0-9, letters A=17..Z=42)."""
    return ord(ch) - 48


def cnpj_check_digits(base12: str) -> str:
    base = _alnum(base12)
    if len(base) != 12 or not re.fullmatch(r"[0-9A-Z]{12}", base):
        raise ValueError("CNPJ base needs 12 alphanumeric characters")
    vals = [_cnpj_value(c) for c in base]
    r = sum(v * w for v, w in zip(vals, _W1)) % 11
    dv1 = 0 if r < 2 else 11 - r
    r = sum(v * w for v, w in zip(vals + [dv1], _W2)) % 11
    dv2 = 0 if r < 2 else 11 - r
    return f"{dv1}{dv2}"


def validate_cnpj(cnpj: str) -> bool:
    s = _alnum(cnpj)
    if not CNPJ_RE.fullmatch(s) or len(set(s)) == 1:
        return False
    return s[12:] == cnpj_check_digits(s[:12])


def normalize_cnpj(cnpj: str) -> str:
    s = _alnum(cnpj)
    if not validate_cnpj(s):
        raise ValueError("invalid CNPJ")
    return s


def format_cnpj(cnpj: str) -> str:
    s = normalize_cnpj(cnpj)
    return f"{s[0:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:14]}"


# --- Boleto: check digits, barcode and typeable line --------------------------------------------

def mod10(digits: str) -> int:
    total = 0
    weight = 2
    for ch in reversed(digits):
        p = int(ch) * weight
        total += p if p < 10 else p - 9
        weight = 1 if weight == 2 else 2
    return (10 - total % 10) % 10


def mod11_barcode(digits43: str) -> int:
    """General check digit of the 44-digit barcode: weights 2..9 from the right; 0, 10 and 11 become 1."""
    if len(digits43) != 43 or not digits43.isdigit():
        raise ValueError("expects the 43 barcode digits without the check digit")
    total = 0
    weight = 2
    for ch in reversed(digits43):
        total += int(ch) * weight
        weight = 2 if weight == 9 else weight + 1
    dv = 11 - total % 11
    return 1 if dv in (0, 10, 11) else dv


def build_barcode(bank: str, factor: int, amount_minor: int, free_field: str) -> str:
    if len(bank) != 3 or not bank.isdigit():
        raise ValueError("bank code has 3 digits")
    if not 1000 <= factor <= 9999:
        raise ValueError("due-date factor is 1000..9999")
    if not 0 <= amount_minor < 10**10:
        raise ValueError("amount does not fit 10 digits")
    if len(free_field) != 25 or not free_field.isdigit():
        raise ValueError("free field has 25 digits")
    body = f"{bank}9{factor:04d}{amount_minor:010d}{free_field}"  # 43 digits, currency code 9 = BRL
    dv = mod11_barcode(body)
    return body[:4] + str(dv) + body[4:]


def validate_barcode(barcode: str) -> bool:
    if len(barcode) != 44 or not barcode.isdigit():
        return False
    return int(barcode[4]) == mod11_barcode(barcode[:4] + barcode[5:])


def typeable_line(barcode: str) -> str:
    if not validate_barcode(barcode):
        raise ValueError("invalid barcode")
    f1 = barcode[0:4] + barcode[19:24]
    f2 = barcode[24:34]
    f3 = barcode[34:44]
    f4 = barcode[4]
    f5 = barcode[5:19]
    return f"{f1}{mod10(f1)}{f2}{mod10(f2)}{f3}{mod10(f3)}{f4}{f5}"


def barcode_from_typeable_line(line: str) -> str:
    d = _digits(line)
    if len(d) != 47:
        raise ValueError("a bank boleto typeable line has 47 digits")
    f1, f2, f3, f4, f5 = d[0:10], d[10:21], d[21:32], d[32], d[33:47]
    for field in (f1, f2, f3):
        if mod10(field[:-1]) != int(field[-1]):
            raise ValueError("field check digit does not match")
    barcode = f1[0:4] + f4 + f5 + f1[4:9] + f2[0:10] + f3[0:10]
    if not validate_barcode(barcode):
        raise ValueError("barcode check digit does not match")
    return barcode


# --- Due-date factor ----------------------------------------------------------------------------

BASE_1997 = date(1997, 10, 7)
RESET_DATE = date(2025, 2, 22)  # FEBRABAN: factor 1000 means 2025-02-22 from this date on


def factor_from_due_date(due: date) -> int:
    if due >= RESET_DATE:
        factor = 1000 + (due - RESET_DATE).days
    else:
        factor = (due - BASE_1997).days
    if not 1000 <= factor <= 9999:
        raise ValueError(f"{due} is outside the representable range")
    return factor


def due_date_from_factor(factor: int, reference: date) -> date:
    """The factor repeats every 9000 days; pick the cycle closest to a reference date (issue or payment)."""
    if not 1000 <= factor <= 9999:
        raise ValueError("due-date factor is 1000..9999")
    old = BASE_1997 + timedelta(days=factor)
    new = RESET_DATE + timedelta(days=factor - 1000)
    return min((old, new), key=lambda d: abs((d - reference).days))
