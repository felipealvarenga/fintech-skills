"""Document validation."""
import re

_WEIGHTS1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_WEIGHTS2 = [6] + _WEIGHTS1


def _check_digit(chars: str, weights: list[int]) -> int:
    total = sum((ord(c) - 48) * w for c, w in zip(chars, weights))
    rem = total % 11
    return 0 if rem < 2 else 11 - rem


def validate_cnpj(value: str) -> bool:
    """Validate a CNPJ (numeric or alphanumeric), with or without punctuation."""
    if not isinstance(value, str):
        return False
    v = re.sub(r"[./-]", "", value.strip()).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", v):
        return False
    if len(set(v)) == 1:
        return False
    d1 = _check_digit(v[:12], _WEIGHTS1)
    d2 = _check_digit(v[:12] + str(d1), _WEIGHTS2)
    return v[12:] == f"{d1}{d2}"
