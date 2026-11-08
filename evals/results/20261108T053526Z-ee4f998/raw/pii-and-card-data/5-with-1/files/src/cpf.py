"""CPF helpers: normalize, validate check digits, mask."""
import re


def normalize(raw):
    return re.sub(r"\D", "", raw or "")


def is_valid(raw):
    cpf = normalize(raw)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        total = sum(int(d) * w for d, w in zip(cpf[:n], range(n + 1, 1, -1)))
        if int(cpf[n]) != (total * 10 % 11) % 10:
            return False
    return True


def mask(raw):
    """Show only the last two digits (check digits): ***.***.***-09"""
    cpf = normalize(raw)
    return "***.***.***-" + cpf[-2:]
