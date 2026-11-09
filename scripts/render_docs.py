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
STRINGS = json.loads((ROOT / "scripts/docs_strings.json").read_text(encoding="utf-8"))


def wilson_half(p, n, z=1.96):
    """Half-width of the 95% Wilson interval for a share p over n trials."""
    import math
    return z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)


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
        parts = folder.name.split("-")
        d["id"] = folder.name
        d["sha"] = parts[1]
        d["kind"] = parts[2] if len(parts) > 2 else "dev"
        out.append(d)
    return out


def pct(x):
    return "n/a" if x is None else f"{round(x * 100)}%"


def rel(skill):
    return skill.relative_to(ROOT).as_posix()


def heldout_sentence(lang, heldout):
    """The held-out set: prompts never read when editing a skill, in evals/heldout/, measured in their own folders."""
    if not heldout:
        return ("A held-out set (prompts never read when editing a skill) is in `evals/heldout/` and has not been measured on this commit yet."
                if lang == "en" else "Um conjunto reservado (prompts nunca lidos ao editar uma skill) está em `evals/heldout/` e ainda não foi medido neste commit.")
    parts = []
    for m, r in heldout.items():
        w, wo = r["pack"]["with"], r["pack"]["without"]
        n = w["passed"] + w["failed"]
        link = f"[evals/results/{r['id']}](evals/results/{r['id']}/summary.md)"
        if lang == "en":
            parts.append(f"`{m}`: **{pct(w['rate'])} with, {pct(wo['rate'])} without** ({w['passed']} against {wo['passed']} of {n}, {link})")
        else:
            parts.append(f"`{m}`: **{pct(w['rate'])} com, {pct(wo['rate'])} sem** ({w['passed']} contra {wo['passed']} de {n}, {link})")
    if lang == "en":
        return "On the held-out set, prompts in `evals/heldout/` that are never read when editing a skill: " + "; ".join(parts) + "."
    return "No conjunto reservado, prompts em `evals/heldout/` nunca lidos ao editar uma skill: " + "; ".join(parts) + "."


def models_on_commit(latest, all_runs=()):
    """Subject model -> its latest development run on the same skills commit as `latest`, in the order the
    models were first measured there. Every README block that quotes a run quotes one run per model."""
    same_commit = [r for r in all_runs if r["sha"] == latest["sha"] and r["kind"] == "dev"] or [latest]
    per_model = {}
    for r in same_commit:
        per_model[r["meta"]["subject_model"]] = r  # sorted ascending, so the latest run per model wins
    return per_model


def headline(lang, latest, prompts, all_runs=()):
    """One sentence per subject model measured on the same skills commit as the latest run (latest run per model)."""
    per_model = models_on_commit(latest, all_runs)
    runs_here = list(per_model.values())
    heldout = {}
    for r in all_runs:
        if r["sha"] == latest["sha"] and r["kind"] == "heldout":
            heldout[r["meta"]["subject_model"]] = r
    def nums(r):
        w, wo = r["pack"]["with"], r["pack"]["without"]
        return pct(w["rate"]), pct(wo["rate"]), w["passed"], wo["passed"], w["passed"] + w["failed"]
    graders = {r["meta"]["grader_model"] for r in runs_here}
    grader = next(iter(graders)) if len(graders) == 1 else None
    links = ", ".join(f"[evals/results/{r['id']}](evals/results/{r['id']}/summary.md)" for r in runs_here)
    models = " and ".join(f"`{m}`" for m in per_model) if lang == "en" else " e ".join(f"`{m}`" for m in per_model)
    if lang == "en":
        scores = "; ".join(f"`{m}`: **{nums(r)[0]} with the skills, {nums(r)[1]} without** ({nums(r)[2]} against {nums(r)[3]} of {nums(r)[4]})" for m, r in per_model.items()) if len(per_model) > 1 else \
                 f"**With the skills, {nums(latest)[0]}. Without them, {nums(latest)[1]}** ({nums(latest)[2]} against {nums(latest)[3]} of {nums(latest)[4]})"
        grader_en = ("a separate session of the same model" if grader and grader in per_model and len(per_model) == 1 else f"`{grader}`" if grader else "a separate grader model")
        return (f"**Measured.** The same {prompts} prompts ran on {models} with and without the skills (skills at\n"
                f"`{latest['sha']}`), and {grader_en} graded each transcript against expectations written before\n"
                f"the run. The score is the share of expectations the grader marked passed; the agent's code is read, not\n"
                f"executed. {scores}. Per skill,\n"
                f"method and raw transcripts: {links}. Those prompts are development prompts: the skills were revised against\n"
                f"earlier runs' failures on them. " + heldout_sentence("en", heldout))
    scores = "; ".join(f"`{m}`: **{nums(r)[0]} com as skills, {nums(r)[1]} sem** ({nums(r)[2]} contra {nums(r)[3]} de {nums(r)[4]})" for m, r in per_model.items()) if len(per_model) > 1 else \
             f"**Com as skills, {nums(latest)[0]}. Sem elas, {nums(latest)[1]}** ({nums(latest)[2]} contra {nums(latest)[3]} de {nums(latest)[4]})"
    grader_pt = ("uma sessão separada do mesmo modelo" if grader and grader in per_model and len(per_model) == 1 else f"`{grader}`" if grader else "um modelo avaliador separado")
    return (f"**Medido.** Os mesmos {prompts} prompts rodaram no {models} com e sem as skills (skills em\n"
            f"`{latest['sha']}`), e {grader_pt} avaliou cada transcrição contra expectativas escritas antes\n"
            f"da execução. A nota é a fração das expectativas que o avaliador marcou como atendidas; o código do agente é\n"
            f"lido, não executado. {scores}. Por skill,\n"
            f"método e transcrições brutas: {links}. Esses prompts são prompts de desenvolvimento: as skills foram revisadas\n"
            f"contra as falhas das execuções anteriores neles. " + heldout_sentence("pt", heldout))


def median_cell(run):
    """Expectations in the median skill cell of a run (the table's cells are about this size)."""
    cells = sorted(v["with"]["passed"] + v["with"]["failed"] for v in run["skills"].values())
    return cells[len(cells) // 2]


def skills_table(lang, latest, all_runs=()):
    """One `with / without` column per subject model measured on the latest skills commit, named in the header."""
    per_model = models_on_commit(latest, all_runs) if latest else {}
    col = "`{m}` with / without" if lang == "en" else "`{m}` com / sem"
    cols = [col.format(m=m) for m in per_model] or (["With / without"] if lang == "en" else ["Com / sem"])
    head = ("| Skill | Use when | " if lang == "en" else "| Skill | Use quando | ") + " | ".join(cols) + (" | Vectors |" if lang == "en" else " | Vetores |")
    rows = [head, "|" + "---|" * (3 + len(cols))]
    for skill in skills_in_order():
        fm = frontmatter(skill)
        use = STRINGS.get(skill.name, {}).get(lang) or fm["description"].split(".")[0]
        cells = []
        for run in per_model.values():
            r = run["skills"].get(skill.name)
            cells.append(f"{pct(r['with_rate'])} / {pct(r['without_rate'])}" if r else "n/a")
        nums = " | ".join(cells) or "n/a"
        py, ts, _ = vectors(skill)
        vec = ", ".join(x for x, has in (("py", py), ("ts", ts)) if has) or ("no" if lang == "en" else "não")
        mark = "†" if skill.name == "fintech-audit" else ""
        rows.append(f"| [{skill.name}]({rel(skill)}/SKILL.md){mark} | {use} | {nums} | {vec} |")
    if per_model:
        n_cell = cell = pack = 0
        for run in per_model.values():  # the widest interval over the models shown, so the caveat holds for every column
            w = run["pack"]["with"]; n_pack = w["passed"] + w["failed"]; n_cell = max(n_cell, median_cell(run))
            cell = max(cell, round(wilson_half(w["rate"], n_cell) * 100)); pack = max(pack, round(wilson_half(w["rate"], n_pack) * 100))
        upto = ("up to " if lang == "en" else "até ") if len(per_model) > 1 else ""
        if lang == "en":
            rows += ["", f"One run per prompt. A cell of about {n_cell} expectations carries {upto}about ±{cell} points (95% Wilson interval); the pack-level numbers carry {upto}about ±{pack}. † fintech-audit was measured without the lint it runs: the eval sandbox has no shell, so its row and the sample report (produced with a shell) are not the same setup."]
        else:
            rows += ["", f"Uma execução por prompt. Uma célula de cerca de {n_cell} expectativas carrega {upto}cerca de ±{cell} pontos (intervalo de Wilson a 95%); os números do pacote carregam {upto}cerca de ±{pack}. † fintech-audit foi medida sem o lint que ela roda: o sandbox do eval não tem shell, então a linha e o relatório de exemplo (produzido com shell) não são o mesmo arranjo."]
    return "\n".join(rows)


def runs_block(lang, all_runs):
    if lang == "en":
        rows = ["| Run | Skills at | Prompts | Subject | With | Without | Lift (points) |", "|---|---|---|---|---|---|---|"]
    else:
        rows = ["| Execução | Skills em | Prompts | Sujeito | Com | Sem | Ganho (pontos) |", "|---|---|---|---|---|---|---|"]
    for d in all_runs:
        w, wo = d["pack"]["with"]["rate"], d["pack"]["without"]["rate"]
        kind = ("development" if d["kind"] == "dev" else "held-out") if lang == "en" else ("desenvolvimento" if d["kind"] == "dev" else "reservado")
        rows.append(f"| [{d['id']}](evals/results/{d['id']}/summary.md) | `{d['sha']}` | {kind} | `{d['meta']['subject_model']}` | {pct(w)} | {pct(wo)} | {round((w - wo) * 100, 1)} |")
    latest = [r for r in all_runs if r["kind"] == "dev"][-1]
    parts = []
    for m, r in models_on_commit(latest, all_runs).items():
        skipped = r.get("method", {}).get("skill_not_opened_with", [])
        n, total = len(skipped), sum(1 for e in r["evals"] if e["condition"] == "with")
        if lang == "en":
            parts.append(f"In all {total} with-skill sessions of the `{m}` run on `{r['sha']}` the agent opened the skill." if n == 0 else
                         f"In {n} of the {total} with-skill sessions of the `{m}` run on `{r['sha']}` the agent never opened the skill; "
                         + ("that session counts" if n == 1 else "those sessions count") + " against the skills.")
        else:
            parts.append(f"Em todas as {total} sessões com skill da execução `{m}` em `{r['sha']}` o agente abriu a skill." if n == 0 else
                         f"Em {n} das {total} sessões com skill da execução `{m}` em `{r['sha']}` o agente nunca abriu a skill; "
                         + ("essa sessão conta" if n == 1 else "essas sessões contam") + " contra as skills.")
    return "\n".join(rows) + "\n\n" + " ".join(parts)


def cut_rule(lang, latest, all_runs=()):
    """The lowest and highest lift, named per subject model measured on the latest skills commit."""
    noise, parts = 0, []
    for m, r in models_on_commit(latest, all_runs).items():
        ranked = sorted(r["skills"].items(), key=lambda kv: kv[1]["lift_points"])
        (lo, lov), (hi, hiv) = ranked[0], ranked[-1]
        noise = max(noise, round(wilson_half(r["pack"]["with"]["rate"], median_cell(r)) * 100))
        if lang == "en":
            parts.append(f"in the `{m}` run on `{r['sha']}` the lowest lift was {lov['lift_points']} points ({lo}) and the highest {hiv['lift_points']} ({hi})")
        else:
            parts.append(f"na execução `{m}` em `{r['sha']}` o menor ganho foi de {lov['lift_points']} pontos ({lo}) e o maior de {hiv['lift_points']} ({hi})")
    lifts = "; ".join(parts); lifts = lifts[0].upper() + lifts[1:]
    if lang == "en":
        return (f"The cut rule stated before the first run: a skill that does not move its own evals by at least 10 points\n"
                f"is folded or removed. {lifts}.\n"
                f"One cell's noise is about ±{noise} points, so the rule is applied over repeated runs, not one.")
    return (f"A regra de corte declarada antes da primeira execução: skill que não move os próprios evals em pelo menos\n"
            f"10 pontos é incorporada a outra ou removida. {lifts}.\n"
            f"O ruído de uma célula é de cerca de ±{noise} pontos, então a regra é aplicada sobre execuções repetidas, não sobre uma.")


def required_names(py_files):
    names = set()
    for f in py_files:
        names |= set(re.findall(r"(?<![A-Za-z0-9_.])m\.([A-Za-z_][A-Za-z0-9_]*)", f.read_text(encoding="utf-8")))
    return sorted(names)


def vectors_table():
    rows = ["| Skill | Python | TypeScript | Environment variable | Names your module must export |", "|---|---|---|---|---|"]
    for skill in skills_in_order():
        py, ts, env = vectors(skill)
        names = ", ".join(f"`{n}`" for n in required_names(py)) or "see the file"
        rows.append(f"| {skill.name} | {', '.join(f'`{rel(p)}`' for p in py) or 'none'} | {', '.join(f'`{rel(p)}`' for p in ts) or 'none'} | {', '.join(f'`{e}`' for e in env)} | {names} |")
    return "\n".join(rows)


def ts_ports():
    have = [s.name for s in skills_in_order() if vectors(s)[1]]
    missing = [s.name for s in skills_in_order() if not vectors(s)[1]]
    text = f"TypeScript ports exist for {', '.join(have)}"
    return text + (f"; {', '.join(missing)} are Python only." if missing else ".")


def named_runs(text):
    """The results folders the README already links. In check mode the README is rendered against those
    runs only, so a results folder can land in its own pull request before the README is re-rendered on
    main; a folder the README does not name yet is reported, not failed."""
    return set(re.findall(r"evals/results/(\d{8}T\d{6}Z-[0-9a-f]{7}(?:-heldout)?)/summary\.md", text))


def render(path, lang, check=False):
    text = (ROOT / path).read_text(encoding="utf-8")
    all_runs = runs()
    if check and lang in ("en", "pt"):
        named = named_runs(text)
        if named:
            unnamed = [r["id"] for r in all_runs if r["id"] not in named]
            all_runs = [r for r in all_runs if r["id"] in named]
            if unnamed:
                print(f"note: {path} does not name {', '.join(unnamed)} yet. Run `python scripts/render_docs.py` to add them.")
    dev_runs = [r for r in all_runs if r["kind"] == "dev"]
    latest = dev_runs[-1] if dev_runs else None
    blocks = {}
    if lang in ("en", "pt"):
        blocks = {"headline": headline(lang, latest, prompt_count(), all_runs), "skills-table": skills_table(lang, latest, all_runs),
                  "runs": runs_block(lang, all_runs), "cut-rule": cut_rule(lang, latest, all_runs)}
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
        new = render(path, lang, check=check)
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
