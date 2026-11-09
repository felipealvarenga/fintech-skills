"""The audit lint reads files only, never through a symlink, and never echoes control characters."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("money_lint", ROOT / "skills/fintech-audit/scripts/money_lint.py")
money_lint = importlib.util.module_from_spec(spec)
sys.modules["money_lint"] = money_lint  # dataclasses resolve the module by name
spec.loader.exec_module(money_lint)


def test_scan_skips_symlinked_files(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("amount: float = 1.0\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "linked.py").symlink_to(outside)
    (repo / "real.py").write_text("price: float = 2.0\n")
    assert {f.path for f in money_lint.scan(repo)} == {"real.py"}


def test_finding_text_drops_control_characters():
    findings = money_lint.scan_text("amount: float = 1.0 \x1b[31mred\x1b[0m\x07\n", "a.py")
    assert findings and findings[0].text == "amount: float = 1.0 [31mred[0m"


def test_very_long_lines_are_skipped():
    assert money_lint.scan_text("x" * 2001 + " amount: float = 1.0\n", "a.py") == []
