"""CNPJ validation (numeric and alphanumeric, Receita Federal algorithm)."""
import re

_W1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_W2 = (6,) + _W1
_FORMATTING = re.compile(r"[.\-/\s]")
_BODY = re.compile(r"[0-9A-Z]{12}[0-9]{2}")


def normalize_cnpj(value: str) -> str:
    """Strip . / - and whitespace and uppercase. Letters are kept."""
    return _FORMATTING.sub("", value).upper()


def _check_digit(chars: str, weights: tuple) -> int:
    total = sum((ord(c) - 48) * w for c, w in zip(chars, weights))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def validate_cnpj(value: str) -> bool:
    if not isinstance(value, str):
        return False
    cnpj = normalize_cnpj(value)
    if not _BODY.fullmatch(cnpj):
        return False
    if len(set(cnpj)) == 1:  # e.g. 00000000000000
        return False
    d1 = _check_digit(cnpj[:12], _W1)
    d2 = _check_digit(cnpj[:12] + str(d1), _W2)
    return cnpj[12:] == f"{d1}{d2}"
