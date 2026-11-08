"""CPF helpers: normalization, check-digit validation, masking."""
import re


def normalize(value):
    return re.sub(r"\D", "", value or "")


def is_valid(value):
    d = normalize(value)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        total = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if int(d[n]) != (total * 10 % 11) % 10:
            return False
    return True


def mask(value):
    """Show only the last two digits: ***.***.***-34"""
    d = normalize(value)
    return "***.***.***-" + d[-2:]
