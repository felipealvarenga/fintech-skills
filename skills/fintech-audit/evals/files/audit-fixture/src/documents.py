"""Document validation."""
import re


def validate_cnpj(value: str) -> bool:
    return bool(re.fullmatch(r"\d{14}", value))
