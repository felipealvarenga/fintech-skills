"""Reference implementation for the pii-and-card-data vectors.

Allowlist redaction for log events, a scanner that finds card and document numbers in text,
Luhn helpers and deterministic synthetic generators, masking, and a schema lint for forbidden
column names. Every number here is synthetic.
"""
from __future__ import annotations

import random
import re

FORBIDDEN_COLUMNS = re.compile(r"(^|_)(pan|card_?number|cc_?num(ber)?|cvv2?|cvc|security_code|track\d?)($|_)", re.I)


# --- redaction -----------------------------------------------------------------------------------

def redact(event: dict, allowlist: set[str]) -> dict:
    """Keep only allowlisted dotted paths. Everything else is dropped, not masked."""
    def walk(node, prefix):
        out = {}
        for key, value in node.items():
            path = f"{prefix}{key}"
            if isinstance(value, dict):
                child = walk(value, path + ".")
                if child:
                    out[key] = child
            elif path in allowlist:
                out[key] = value
        return out
    return walk(event, "")


# --- Luhn and scanning ------------------------------------------------------------------------------

def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D", "", number)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def luhn_check_digit(partial: str) -> int:
    for d in range(10):
        if luhn_valid(partial + str(d)):
            return d
    raise ValueError("unreachable")


def make_test_pan(prefix: str = "4242", length: int = 16, seed: int = 0) -> str:
    rng = random.Random(seed)
    body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(length - len(prefix) - 1))
    return body + str(luhn_check_digit(body))


def _cpf_valid(d: str) -> bool:
    if len(d) != 11 or len(set(d)) == 1:
        return False
    nums = [int(c) for c in d]
    for n in (9, 10):
        r = sum(nums[i] * (n + 1 - i) for i in range(n)) % 11
        if (0 if r < 2 else 11 - r) != nums[n]:
            return False
    return True


def make_test_cpf(seed: int = 0) -> str:
    rng = random.Random(seed)
    while True:
        base = [rng.randint(0, 9) for _ in range(9)]
        if len(set(base)) == 1:
            continue
        nums = list(base)
        for n in (9, 10):
            r = sum(nums[i] * (n + 1 - i) for i in range(n)) % 11
            nums.append(0 if r < 2 else 11 - r)
        return "".join(map(str, nums))


PAN_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
CPF_RE = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def scan(text: str) -> list[str]:
    """Finding codes for data that must never be in a log: pan, cpf, email."""
    findings = []
    for match in PAN_RE.finditer(text):
        if luhn_valid(match.group(0)):
            findings.append("pan")
            break
    for match in CPF_RE.finditer(text):
        if _cpf_valid(re.sub(r"\D", "", match.group(0))):
            findings.append("cpf")
            break
    if EMAIL_RE.search(text):
        findings.append("email")
    return findings


# --- masking and schema lint -------------------------------------------------------------------------

def mask_pan(pan: str) -> str:
    d = re.sub(r"\D", "", pan)
    if not luhn_valid(d):
        raise ValueError("not a card number")
    return "*" * (len(d) - 4) + d[-4:]


def mask_document(doc: str, keep: int = 2) -> str:
    d = re.sub(r"\W", "", doc)
    if len(d) <= keep:
        raise ValueError("too short to mask")
    return "*" * (len(d) - keep) + d[-keep:]


def schema_lint(columns: list[str]) -> list[str]:
    return [c for c in columns if FORBIDDEN_COLUMNS.search(c)]
