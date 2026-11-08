#!/usr/bin/env python3
"""Deterministic lint for money code. Prints leads, not verdicts: every hit must be confirmed by
reading the code. Works on Python, JavaScript, TypeScript, Go, Ruby, Java, SQL and config files.

usage: money_lint.py <path> [--json]
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

MONEY = r"(amount|price|total|balance|fee|interest|installment|cents|minor|payout|refund|charge|subtotal|tax|discount|credit|debit)"
SKIP_DIRS = {".git", ".claude", ".agents", ".codex", "node_modules", ".venv", "venv", "vendor", "dist", "build", "__pycache__", ".pytest_cache", "target"}
EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".kt", ".sql", ".cs", ".php"}

RULES: list[tuple[str, re.Pattern, str, str]] = [
    ("FLOAT_MONEY", re.compile(rf"\b{MONEY}\w*\s*:\s*(float|Float|number|double|Double|DECIMAL\(\s*\d+\s*,\s*\d+\s*\)\s*$)|Column\(\s*Float|FloatField\(|\bfloat\(\s*\w*{MONEY}|: *float\s*=|REAL|DOUBLE PRECISION", re.I),
     "money-arithmetic", "1: an amount is an integer count of minor units plus a currency"),
    ("DIV100", re.compile(rf"\b\w*{MONEY}\w*\)?\s*[*/]\s*100(\.0+)?\b|\b100(\.0+)?\s*\*\s*\w*{MONEY}|/\s*100\b.*{MONEY}|{MONEY}.*?/\s*100\b", re.I),
     "money-arithmetic", "2: the exponent comes from ISO 4217, never a hardcoded 100"),
    ("ROUND_MONEY", re.compile(rf"\b(round|Math\.round|toFixed|number_format)\s*\(.*{MONEY}|\b{MONEY}\w*.*\b(round|toFixed)\s*\(", re.I),
     "money-arithmetic", "4: one rounding policy, named, applied at one point"),
    ("RATE_FLOAT", re.compile(r"\b\w*(rate|fee_pct|mdr|apr|percent)\w*\s*[:=]\s*0\.\d+\b", re.I),
     "money-arithmetic", "6: rates are decimals from a string, never floats"),
    ("RANDOM_IDEMPOTENCY", re.compile(r"(idempoten\w*|Idempotency-Key)[^\n]{0,80}(uuid4?\(\)|randomUUID\(|random\.|secrets\.token|nanoid\()|(uuid4?\(\)|randomUUID\(|nanoid\()[^\n]{0,80}idempoten", re.I),
     "idempotent-payments", "4: the outbound key is derived from the operation id, never random per attempt"),
    ("BALANCE_UPDATE", re.compile(r"UPDATE\s+\w+\s+SET\s+\w*balance\w*\s*=|\bbalance\w*\s*(\+=|-=)|\.balance\s*=\s*\w+\.balance\s*[-+]", re.I),
     "double-entry-ledger", "1 and 4: entries are immutable and balances are derived"),
    ("BODY_LOG", re.compile(r"\b(log\w*|logger|console)\.(info|debug|warn|warning|error|log)\s*\(.*(request\.(json|body|data|get_json)|req\.body|payload|response\.(json|body|text)|resp\.(json|text))", re.I),
     "pii-and-card-data", "3: redact by allowlist at the logger; never log payment bodies"),
    ("PARSED_BODY_VERIFY", re.compile(r"construct_event\s*\(\s*(json\.dumps|JSON\.stringify)|constructEvent\s*\(\s*JSON\.stringify|get_json\(\)[\s\S]{0,200}construct_event", re.I),
     "webhook-handling", "1: verify the signature on the raw body, before parsing"),
    ("CVV_FIELD", re.compile(r"\b(cvv2?|cvc|security_code|card_number|cardnumber|pan)\b\s*[:=,]|column\(\s*['\"](cvv|cvc|card_number|pan)", re.I),
     "pii-and-card-data", "1: card numbers never enter your systems; the CVV is never stored"),
    ("DIGITS_ONLY_CNPJ", re.compile(r"cnpj[\s\S]{0,120}\\d\{14\}|\\d\{14\}[\s\S]{0,40}cnpj|cnpj[\s\S]{0,120}isdigit\(\)", re.I),
     "brazil-payment-rails", "12: CNPJs issued from July 2026 contain letters; validate check digits"),
    ("WALL_CLOCK_MONEY", re.compile(rf"(def|function|const|func)\s+\w*(settle|settlement|due|maturity|payout|accru|interest|{MONEY})\w*[\s\S]{{0,240}}?(datetime\.now\(|datetime\.utcnow\(|date\.today\(|Date\.now\(|new Date\(\)|time\.time\()", re.I),
     "money-tests", "7: inject the clock; settlement and due dates come from an injected time"),
    ("PAID_ON_ISSUE", re.compile(r"(boleto|invoice|slip)[\s\S]{0,160}status\s*=\s*['\"]paid['\"]|generate_boleto[\s\S]{0,200}paid", re.I),
     "brazil-payment-rails", "6: a boleto is pending until the return confirms it"),
]


@dataclass
class Finding:
    code: str
    path: str
    line: int
    text: str
    skill: str
    rule: str


def scan_text(text: str, path: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for code, pattern, skill, rule in RULES:
        if code in ("PARSED_BODY_VERIFY", "DIGITS_ONLY_CNPJ", "PAID_ON_ISSUE", "WALL_CLOCK_MONEY"):
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.end() - 1) + 1
                findings.append(Finding(code, path, line, lines[line - 1].strip()[:140], skill, rule))
            continue
        for number, line_text in enumerate(lines, start=1):
            if pattern.search(line_text):
                findings.append(Finding(code, path, number, line_text.strip()[:140], skill, rule))
    seen = set()
    unique = []
    for f in findings:
        key = (f.code, f.path, f.line)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return sorted(unique, key=lambda f: (f.path, f.line, f.code))


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    for p in files:
        if any(part in SKIP_DIRS for part in p.parts) or p.suffix not in EXTS:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(root)) if root.is_dir() else p.name
        findings.extend(scan_text(text, rel))
    return findings


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    root = Path(argv[0])
    as_json = "--json" in argv
    findings = scan(root)
    if as_json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for f in findings:
            print(f"{f.code:20s} {f.path}:{f.line}  {f.text}\n{'':20s} -> {f.skill} rule {f.rule}")
        print(f"\n{len(findings)} leads in {root}. Confirm each one by reading the code.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
