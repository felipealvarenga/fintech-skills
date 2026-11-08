#!/usr/bin/env python3
"""Render the generated blocks in README.md, README.pt-BR.md and evals/README.md from the sources of
truth: skills/*/SKILL.md frontmatter, the vectors on disk, evals/*/evals.json and
evals/results/*/results.json. Blocks sit between `<!-- generated:NAME -->` and
`<!-- /generated:NAME -->`. Run without arguments to rewrite the files; `--check` fails when a
file differs from its rendering, so the docs cannot drift from the code."""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FILES = {"README.md": "en", "README.pt-BR.md": "pt", "evals/README.md": "evals"}


def skills_in_order():
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    return [ROOT / p for p in plugin["skills"]]


def frontmatter(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    return yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL).group(1))


def vectors(skill):
    folder = skill / "evals/vectors"
    py = sorted(folder.glob("test_*.py")) if folder.exists() else []
    ts = sorted(folder.glob("*.test.ts")) if folder.exists() else []
    env = []
    for f in py + ts:
        env += re.findall(r'(?:environ\.get|environ|getenv|_load)\(?\[?"([A-Z_]+)"', f.read_text(encoding="utf-8"))
        env += re.findall(r"process\.env\.([A-Z_]+)", f.read_text(encoding="utf-8"))
    return py, ts, sorted(set(env))


def prompt_count():
    return sum(len(json.loads((s / "evals/evals.json").read_text(encoding="utf-8"))["evals"]) for s in skills_in_order())


def runs():
    out = []
    for folder in sorted((ROOT / "evals/results").iterdir()):
        f = folder / "results.json"
        if not f.is_file():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        d["id"] = folder.name
        d["sha"] = folder.name.split("-", 1)[1]
        out.append(d)
    return out


def pct(x):
    return "n/a" if x is None else f"{round(x * 100)}%"


def rel(skill):
    return skill.relative_to(ROOT).as_posix()


def headline(lang, latest, prompts):
    w, wo = latest["pack"]["with"], latest["pack"]["without"]
    n_w, n_wo = w["passed"] + w["failed"], wo["passed"] + wo["failed"]
    of = f"{n_w}" if n_w == n_wo else f"{n_w} and {n_wo}" if lang == "en" else f"{n_w} e {n_wo}"
    link = f"[evals/results/{latest['id']}](evals/results/{latest['id']}/summary.md)"
    model = f"`{latest['meta']['subject_model']}`"
    if lang == "en":
        return (f"**Measured.** The same {prompts} prompts ran on {model} with and without the skills, and a second\n"
                f"model graded the transcripts against expectations written before the run. **With the skills, {pct(w['rate'])}\n"
                f"of expectations passed. Without them, {pct(wo['rate'])}** ({w['passed']} against {wo['passed']} of {of}). Per skill, method and raw\n"
                f"transcripts: {link}.")
    return (f"**Medido.** Os mesmos {prompts} prompts rodaram no {model} com e sem as skills, e um segundo modelo\n"
            f"avaliou as transcrições contra expectativas escritas antes da execução. **Com as skills, {pct(w['rate'])} das\n"
            f"expectativas passaram. Sem elas, {pct(wo['rate'])}** ({w['passed']} contra {wo['passed']} de {of}). Por skill, método e transcrições\n"
            f"brutas: {link}.")


def skills_table(lang, latest):
    head = ("| Skill | Use when | With / without | Vectors |" if lang == "en" else "| Skill | Use quando | Com / sem | Vetores |")
    rows = [head, "|---|---|---|---|"]
    for skill in skills_in_order():
        fm = frontmatter(skill)
        meta = fm.get("metadata") or {}
        use = meta.get("use_when" if lang == "en" else "use_when_pt") or fm["description"].split(".")[0]
        r = latest["skills"].get(skill.name) if latest else None
        nums = f"{pct(r['with_rate'])} / {pct(r['without_rate'])}" if r else "n/a"
        py, ts, _ = vectors(skill)
        vec = ", ".join(x for x, has in (("py", py), ("ts", ts)) if has) or ("no" if lang == "en" else "não")
        rows.append(f"| [{skill.name}]({rel(skill)}/SKILL.md) | {use} | {nums} | {vec} |")
    return "\n".join(rows)


def runs_block(lang, all_runs):
    if lang == "en":
        rows = ["| Run | Skills at | Subject | With | Without | Lift (points) |", "|---|---|---|---|---|---|"]
    else:
        rows = ["| Execução | Skills em | Sujeito | Com | Sem | Ganho (pontos) |", "|---|---|---|---|---|---|"]
    for d in all_runs:
        w, wo = d["pack"]["with"]["rate"], d["pack"]["without"]["rate"]
        rows.append(f"| [{d['id']}](evals/results/{d['id']}/summary.md) | `{d['sha']}` | `{d['meta']['subject_model']}` | {pct(w)} | {pct(wo)} | {round((w - wo) * 100, 1)} |")
    latest = all_runs[-1]
    skipped = latest.get("method", {}).get("skill_not_opened_with", [])
    n, total = len(skipped), sum(1 for e in latest["evals"] if e["condition"] == "with")
    if lang == "en":
        tail = (f"In all {total} with-skill sessions of the latest run the agent opened the skill." if n == 0 else
                f"In {n} of the {total} with-skill sessions of the latest run the agent never opened the skill; "
                + ("that session counts" if n == 1 else "those sessions count") + " against the skills.")
    else:
        tail = (f"Em todas as {total} sessões com skill da última execução o agente abriu a skill." if n == 0 else
                f"Em {n} das {total} sessões com skill da última execução o agente nunca abriu a skill; "
                + ("essa sessão conta" if n == 1 else "essas sessões contam") + " contra as skills.")
    return "\n".join(rows) + "\n\n" + tail


def cut_rule(lang, latest):
    ranked = sorted(latest["skills"].items(), key=lambda kv: kv[1]["lift_points"])
    (lo, lov), (hi, hiv) = ranked[0], ranked[-1]
    if lang == "en":
        return (f"A skill that does not move its own evals by at least 10 points gets folded or removed; in the latest\n"
                f"run the lowest lift was {lov['lift_points']} points ({lo}) and the highest {hiv['lift_points']} ({hi}).")
    return (f"Skill que não move os próprios evals em pelo menos 10 pontos é incorporada a outra ou removida; na\n"
            f"última execução o menor ganho foi de {lov['lift_points']} pontos ({lo}) e o maior de {hiv['lift_points']} ({hi}).")


def vectors_table():
    rows = ["| Skill | Python | TypeScript | Environment variable |", "|---|---|---|---|"]
    for skill in skills_in_order():
        py, ts, env = vectors(skill)
        rows.append(f"| {skill.name} | {', '.join(f'`{rel(p)}`' for p in py) or 'none'} | {', '.join(f'`{rel(p)}`' for p in ts) or 'none'} | {', '.join(f'`{e}`' for e in env)} |")
    return "\n".join(rows)


def ts_ports():
    have = [s.name for s in skills_in_order() if vectors(s)[1]]
    missing = [s.name for s in skills_in_order() if not vectors(s)[1]]
    text = f"TypeScript ports exist for {', '.join(have)}"
    return text + (f"; {', '.join(missing)} are Python only." if missing else ".")


def render(path, lang):
    text = (ROOT / path).read_text(encoding="utf-8")
    all_runs = runs()
    latest = all_runs[-1] if all_runs else None
    blocks = {}
    if lang in ("en", "pt"):
        blocks = {"headline": headline(lang, latest, prompt_count()), "skills-table": skills_table(lang, latest),
                  "runs": runs_block(lang, all_runs), "cut-rule": cut_rule(lang, latest)}
    else:
        blocks = {"vectors-table": vectors_table(), "ts-ports": ts_ports()}
    for name, body in blocks.items():
        pattern = re.compile(rf"<!-- generated:{name} -->\n?.*?\n?<!-- /generated:{name} -->", re.DOTALL)
        if not pattern.search(text):
            sys.exit(f"{path}: marker block '{name}' missing")
        text = pattern.sub(lambda m: f"<!-- generated:{name} -->\n{body}\n<!-- /generated:{name} -->", text, count=1)
    return text


def main(argv):
    check = "--check" in argv
    stale = []
    for path, lang in FILES.items():
        new = render(path, lang)
        if new != (ROOT / path).read_text(encoding="utf-8"):
            stale.append(path)
            if not check:
                (ROOT / path).write_text(new, encoding="utf-8")
    if check and stale:
        print("ERROR: generated docs are stale, run `python scripts/render_docs.py`:", ", ".join(stale))
        return 1
    print("docs rendered" if not check else "generated docs match", ", ".join(FILES))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
