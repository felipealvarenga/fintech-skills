#!/usr/bin/env python3
"""Validate every skill: SKILL.md frontmatter per the Agent Skills spec, evals/evals.json shape,
and that plugin.json lists exactly the skills on disk."""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
MIN_EVALS = 6
errors = []


def check_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{skill_dir.name}: SKILL.md missing")
        return
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        errors.append(f"{skill_dir.name}: no YAML frontmatter")
        return
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"{skill_dir.name}: frontmatter is not valid YAML ({str(exc).splitlines()[0]})")
        return
    if not isinstance(fm, dict):
        errors.append(f"{skill_dir.name}: frontmatter is not a mapping")
        return
    extra = set(fm) - ALLOWED
    if extra:
        errors.append(f"{skill_dir.name}: unexpected frontmatter keys {sorted(extra)}")
    name = fm.get("name")
    desc = fm.get("description")
    if name != skill_dir.name:
        errors.append(f"{skill_dir.name}: name '{name}' must equal the folder name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", name or ""):
        errors.append(f"{skill_dir.name}: name must be kebab-case, 64 chars max")
    if not isinstance(desc, str) or not desc.strip():
        errors.append(f"{skill_dir.name}: description missing")
    elif len(desc) > 1024:
        errors.append(f"{skill_dir.name}: description is {len(desc)} chars, max 1024")
    evals = skill_dir / "evals" / "evals.json"
    if not evals.exists():
        errors.append(f"{skill_dir.name}: evals/evals.json missing")
        return
    data = json.loads(evals.read_text(encoding="utf-8"))
    if data.get("skill_name") != name:
        errors.append(f"{skill_dir.name}: evals.json skill_name does not match")
    ids = set()
    for ev in data.get("evals", []):
        for key in ("id", "prompt", "expected_output", "expectations"):
            if key not in ev:
                errors.append(f"{skill_dir.name}: eval missing '{key}'")
        if ev.get("id") in ids:
            errors.append(f"{skill_dir.name}: duplicate eval id {ev.get('id')}")
        ids.add(ev.get("id"))
        if not ev.get("expectations"):
            errors.append(f"{skill_dir.name}: eval {ev.get('id')} has no expectations")
        for rel in ev.get("files", []):
            if not (skill_dir / rel).is_file():
                errors.append(f"{skill_dir.name}: eval {ev.get('id')} references missing file {rel}")
    if len(data.get("evals", [])) < MIN_EVALS:
        errors.append(f"{skill_dir.name}: fewer than {MIN_EVALS} evals")


def check_heldout(skill_dir: Path) -> None:
    source = ROOT / "evals" / "heldout" / f"{skill_dir.name}.json"
    if not source.exists():
        return
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("skill_name") != skill_dir.name:
        errors.append(f"heldout {skill_dir.name}: skill_name does not match")
    ids = set()
    for ev in data.get("evals", []):
        for key in ("id", "prompt", "expected_output", "expectations"):
            if key not in ev:
                errors.append(f"heldout {skill_dir.name}: eval missing '{key}'")
        if ev.get("id") in ids:
            errors.append(f"heldout {skill_dir.name}: duplicate eval id {ev.get('id')}")
        ids.add(ev.get("id"))
        for rel in ev.get("files", []):
            if not (ROOT / "evals" / "heldout" / "files" / skill_dir.name / rel).is_file():
                errors.append(f"heldout {skill_dir.name}: eval {ev.get('id')} references missing file {rel}")
    if len(data.get("evals", [])) < 2:
        errors.append(f"heldout {skill_dir.name}: fewer than 2 evals")


def check_symlinks(root: Path) -> list[str]:
    """A skill installs as plain files; a symlink under skills/ could carry a file from outside the pack."""
    return [f"{p.relative_to(root.parent).as_posix()}: symlinks are not allowed under skills/"
            for p in sorted(root.rglob("*")) if p.is_symlink()]


def main() -> int:
    skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    for s in skills:
        check_skill(s)
        check_heldout(s)
    errors.extend(check_symlinks(ROOT / "skills"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    listed = {Path(p).name for p in plugin["skills"]}
    on_disk = {s.name for s in skills}
    if listed != on_disk:
        errors.append(f"plugin.json skills differ from disk: missing {sorted(on_disk - listed)}, extra {sorted(listed - on_disk)}")
    import render_docs
    if render_docs.main(["--check"]) != 0:
        errors.append("generated docs are stale (python scripts/render_docs.py)")
    for e in errors:
        print("ERROR:", e)
    print(f"{len(skills)} skills checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
