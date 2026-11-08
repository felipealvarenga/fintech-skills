"""Reference implementation for the money-tests vectors.

A static checker for the test smells money code suffers from, and the mutation kill-rate
arithmetic that money-tests asks for in every pull request.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    code: str
    line: int
    detail: str


WALL_CLOCK = re.compile(r"\b(datetime\.now|datetime\.utcnow|date\.today|time\.time|timezone\.now)\s*\(")
SLEEP = re.compile(r"\b(time\.)?sleep\s*\(")
LIVE_HTTP = re.compile(r"\b(requests|httpx|urllib\.request|stripe|boto3)\.")
FAKES = re.compile(r"\b(responses|respx|vcr|httpretty|requests_mock|monkeypatch|mock|Fake\w*|stub)\b", re.I)
UNSEEDED_RANDOM = re.compile(r"\brandom\.(random|randint|choice|shuffle|uniform)\s*\(")
SEEDED = re.compile(r"\b(random\.seed|Random)\s*\(")
APPROX_MONEY = re.compile(r"\b(approx|assertAlmostEqual|isclose)\b")
MONEY_NAME = re.compile(r"\b(amount|price|total|balance|fee|interest|installment|cents|minor)\b", re.I)


def lint_tests(source: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = source.splitlines()
    for number, text in enumerate(lines, start=1):
        if WALL_CLOCK.search(text):
            findings.append(Finding("wall-clock", number, text.strip()))
        if SLEEP.search(text):
            findings.append(Finding("sleep", number, text.strip()))
        if LIVE_HTTP.search(text) and not FAKES.search(text):
            findings.append(Finding("live-network", number, text.strip()))
        if UNSEEDED_RANDOM.search(text) and not SEEDED.search(source):
            findings.append(Finding("unseeded-random", number, text.strip()))
        if APPROX_MONEY.search(text) and MONEY_NAME.search(text):
            findings.append(Finding("approximate-money", number, text.strip()))
        if re.search(r"^\s*assert\s+\w+(\.\w+)*\s+is\s+not\s+None\s*$", text):
            findings.append(Finding("weak-assertion", number, text.strip()))
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        findings.append(Finding("syntax-error", exc.lineno or 0, str(exc)))
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(node))
            uses_raises = any(isinstance(n, ast.Attribute) and n.attr == "raises" for n in ast.walk(node))
            if not has_assert and not uses_raises:
                findings.append(Finding("no-assertion", node.lineno, node.name))
    return sorted(findings, key=lambda f: (f.line, f.code))


def kill_rate(killed: int, survived: int, errors: int = 0, timeouts: int = 0) -> float | None:
    """Mutation score over decided mutants only. Errors and timeouts never count as killed."""
    for value in (killed, survived, errors, timeouts):
        if value < 0:
            raise ValueError("counts are non-negative")
    decided = killed + survived
    if decided == 0:
        return None
    return round(killed / decided, 4)


def meets_gate(rate: float | None, threshold: float = 0.8) -> bool:
    return rate is not None and rate >= threshold
