"""Test vectors for fintech-audit: the lint finds every planted defect and nothing on the clean sample.

Run: `pytest skills/fintech-audit`. To test your own lint, set AUDIT_LINT to a script that takes a
path and prints JSON findings with `code` and `path` fields when called with `--json`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
LINT = os.environ.get("AUDIT_LINT") or str(SKILL / "scripts" / "money_lint.py")
FIXTURE = SKILL / "evals" / "files" / "audit-fixture"
CLEAN = SKILL / "evals" / "files" / "clean-sample"

PLANTED = {
    ("FLOAT_MONEY", "src/billing.py"), ("ROUND_MONEY", "src/billing.py"), ("DIV100", "src/billing.py"),
    ("RANDOM_IDEMPOTENCY", "src/charges.py"), ("RATE_FLOAT", "src/charges.py"),
    ("BALANCE_UPDATE", "src/wallet.py"),
    ("BODY_LOG", "src/webhooks.py"), ("PARSED_BODY_VERIFY", "src/webhooks.py"),
    ("CVV_FIELD", "src/models.py"), ("DIGITS_ONLY_CNPJ", "src/documents.py"),
    ("PAID_ON_ISSUE", "src/boleto.py"), ("WALL_CLOCK_MONEY", "src/settlement.py"),
}


def run(path: Path) -> list[dict]:
    proc = subprocess.run([sys.executable, LINT, str(path), "--json"], capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stderr
    return json.loads(proc.stdout)


def test_every_planted_defect_is_found():
    found = {(f["code"], f["path"]) for f in run(FIXTURE)}
    missing = PLANTED - found
    assert not missing, f"lint missed {sorted(missing)}"


def test_findings_carry_line_skill_and_rule():
    for f in run(FIXTURE):
        assert f["line"] >= 1 and f["skill"] and f["rule"] and f["text"]


def test_clean_sample_has_no_findings():
    assert run(CLEAN) == []


def test_exit_code_signals_findings():
    assert subprocess.run([sys.executable, LINT, str(FIXTURE)], capture_output=True).returncode == 1
    assert subprocess.run([sys.executable, LINT, str(CLEAN)], capture_output=True).returncode == 0
