"""Document validation."""
import re

_CNPJ_RE = re.compile(r"[0-9A-Z]{12}[0-9]{2}")


def _cnpj_digit(base: str) -> int:
    # weights cycle 2..9 from the right; char value is ord(c) - 48 (digits 0-9, letters 17-42)
    total = sum((ord(c) - 48) * (2 + i % 8) for i, c in enumerate(reversed(base)))
    r = total % 11
    return 0 if r < 2 else 11 - r


def validate_cnpj(value: str) -> bool:
    """Numeric and alphanumeric (from July 2026) CNPJ with check digits."""
    v = re.sub(r"[.\-/]", "", value or "").upper()
    if not _CNPJ_RE.fullmatch(v) or len(set(v)) == 1:
        return False
    d1 = _cnpj_digit(v[:12])
    d2 = _cnpj_digit(v[:12] + str(d1))
    return v[12:] == f"{d1}{d2}"
