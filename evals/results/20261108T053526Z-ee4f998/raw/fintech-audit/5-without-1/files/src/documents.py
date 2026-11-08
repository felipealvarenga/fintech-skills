"""Document validation."""
import re


def validate_cnpj(value: str) -> bool:
    """Validate a CNPJ (formatted or not), including check digits."""
    if not re.fullmatch(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", value):
        return False
    digits = [int(c) for c in re.sub(r"\D", "", value)]
    if len(set(digits)) == 1:
        return False
    for n in (12, 13):
        weights = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if n == 12
                   else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        s = sum(d * w for d, w in zip(digits[:n], weights))
        check = 0 if s % 11 < 2 else 11 - s % 11
        if digits[n] != check:
            return False
    return True
