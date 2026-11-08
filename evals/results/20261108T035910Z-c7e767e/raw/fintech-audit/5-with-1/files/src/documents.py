"""Document validation."""
import re

_CNPJ_RE = re.compile(r"[0-9A-Z]{12}[0-9]{2}")


def _dv(base: str) -> int:
    weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
    total = sum((ord(c) - 48) * w for c, w in zip(base, weights))
    r = total % 11
    return 0 if r < 2 else 11 - r


def validate_cnpj(value: str) -> bool:
    """Numeric and alphanumeric (July 2026) CNPJ, with check digits."""
    v = re.sub(r"[.\-/]", "", value or "").upper()
    if not _CNPJ_RE.fullmatch(v) or len(set(v)) == 1:
        return False
    d1 = _dv(v[:12])
    d2 = _dv(v[:12] + str(d1))
    return v[12:] == f"{d1}{d2}"
