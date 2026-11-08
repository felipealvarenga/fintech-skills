"""CPF validation."""
import re


def valid_cpf(value):
    return bool(re.fullmatch(r"\d{11}", value))
