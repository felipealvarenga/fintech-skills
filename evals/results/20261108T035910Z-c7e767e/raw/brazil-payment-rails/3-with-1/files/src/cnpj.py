"""CNPJ validation, numeric and alphanumeric (registrations from July 2026)."""
import re

_W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_W2 = [6] + _W1


def normalize_cnpj(value: str) -> str:
    """Strip formatting (. / -) and whitespace, uppercase letters."""
    return re.sub(r"[.\-/\s]", "", value).upper()


def _check_digit(chars: str, weights: list[int]) -> int:
    total = sum((ord(c) - 48) * w for c, w in zip(chars, weights))
    rem = total % 11
    return 0 if rem < 2 else 11 - rem


def validate_cnpj(value: str) -> bool:
    cnpj = normalize_cnpj(value)
    # 12 alphanumeric base positions + 2 numeric check digits
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", cnpj):
        return False
    if len(set(cnpj)) == 1:  # e.g. 00000000000000
        return False
    d1 = _check_digit(cnpj[:12], _W1)
    d2 = _check_digit(cnpj[:12] + str(d1), _W2)
    return cnpj[12:] == f"{d1}{d2}"
