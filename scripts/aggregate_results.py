#!/usr/bin/env python3
"""Aggregate a graded run into the committed form: results.json (pack, per skill, per eval; the schema
scripts/render_docs.py reads), skills/<skill>.json (one record per eval and condition) and a summary.md
with the tables. The input is one run folder from scripts/run_evals.py, or a folder of run folders when
the skills were run one invocation at a time.

usage: python3 scripts/aggregate_results.py <run-dir-or-parent> <out-dir> [--note "text"]
"""
import json
import pathlib
import sys
from collections import defaultdict


def rate(passed, failed):
    total = passed + failed
    return None if total == 0 else passed / total


def main(argv):
    src = pathlib.Path(argv[0])
    out = pathlib.Path(argv[1])
    note = argv[argv.index("--note") + 1] if "--note" in argv else ""
    out.mkdir(parents=True, exist_ok=True)
    skills = {}
    meta = None
    if any(f.name != "results.json" for f in src.glob("*.json")):
        run_dirs = [src]  # one run folder from the runner
    elif (src / "skills").is_dir():
        run_dirs = [src / "skills"]  # a committed results folder
    else:
        run_dirs = sorted(p for p in src.iterdir() if p.is_dir())  # one folder per skill invocation
    (out / "skills").mkdir(exist_ok=True)
    for run_dir in run_dirs:
        for f in sorted(run_dir.glob("*.json")):
            if f.name == "results.json":
                continue
            d = json.load(open(f))
            skill = d["skill"]
            if skill in skills:  # keep the latest run per skill
                continue
            skills[skill] = {"run_id": d["run_id"], "git_sha": d["git_sha"], "installed_paths": d["installed_paths"], "records": d["records"]}
            (out / "skills" / f"{skill}.json").write_text(f.read_text())
            meta = meta or {k: d[k] for k in ("subject_model", "grader_model", "git_sha") if k in d}
    per_skill = {}
    totals = defaultdict(lambda: {"passed": 0, "failed": 0, "error": 0, "subject_tokens": 0, "grader_tokens": 0, "wall": 0.0, "max_turns": 0})
    rows_eval = []
    for skill, data in sorted(skills.items()):
        agg = {c: {"passed": 0, "failed": 0, "error": 0, "subject_tokens": 0, "grader_tokens": 0, "wall": 0.0, "max_turns": 0} for c in ("with", "without")}
        for r in data["records"]:
            c = r["condition"]
            counts = {"passed": 0, "failed": 0, "error": 0}
            for v in r["verdicts"]:
                counts[v["status"]] += 1
            for k, n in counts.items():
                agg[c][k] += n
                totals[c][k] += n
            for role, key in (("subject", "subject_tokens"), ("grader", "grader_tokens")):
                sess = r.get(role) or {}
                toks = sum((sess.get("tokens") or {}).values())
                agg[c][key] += toks
                totals[c][key] += toks
                agg[c]["wall"] += sess.get("wall_time") or 0
                totals[c]["wall"] += sess.get("wall_time") or 0
            if (r.get("subject") or {}).get("stop_reason") == "max_turns":
                agg[c]["max_turns"] += 1
                totals[c]["max_turns"] += 1
            rows_eval.append({"skill": skill, "eval_id": r["eval_id"], "condition": c, **counts,
                              "subject_stop": (r.get("subject") or {}).get("stop_reason"), "subject_error": (r.get("subject") or {}).get("error")})
        w, wo = rate(agg["with"]["passed"], agg["with"]["failed"]), rate(agg["without"]["passed"], agg["without"]["failed"])
        per_skill[skill] = {"with": agg["with"], "without": agg["without"], "with_rate": w, "without_rate": wo,
                            "lift_points": None if w is None or wo is None else round((w - wo) * 100, 1), "run_id": data["run_id"]}
    pack = {c: {**totals[c], "rate": rate(totals[c]["passed"], totals[c]["failed"])} for c in ("with", "without")}
    results = {"meta": meta, "note": note, "pack": pack, "skills": per_skill, "evals": rows_eval}
    (out / "results.json").write_text(json.dumps(results, indent=2))

    def pct(x):
        return "n/a" if x is None else f"{x * 100:.1f}%"

    lines = ["# fintech-skills evaluation results", ""]
    if meta:
        lines += [f"subject model: {meta.get('subject_model')} · grader model: {meta.get('grader_model')} · runner sha: {meta.get('git_sha')}", ""]
    if note:
        lines += [note, ""]
    lines += ["## Pack level", "", "| Condition | Pass rate | Passed | Failed | Errors | Subject tokens | Grader tokens | Wall seconds |", "|---|---|---|---|---|---|---|---|"]
    for c in ("with", "without"):
        t = pack[c]
        lines.append(f"| {c} | {pct(t['rate'])} | {t['passed']} | {t['failed']} | {t['error']} | {t['subject_tokens']} | {t['grader_tokens']} | {t['wall']:.0f} |")
    lines += ["", "## Per skill", "", "| Skill | With | Without | Lift (points) | Errors with/without | Run id |", "|---|---|---|---|---|---|"]
    for skill, s in sorted(per_skill.items(), key=lambda kv: -(kv[1]["lift_points"] or -999)):
        lines.append(f"| {skill} | {pct(s['with_rate'])} | {pct(s['without_rate'])} | {s['lift_points'] if s['lift_points'] is not None else 'n/a'} | {s['with']['error']}/{s['without']['error']} | {s['run_id']} |")
    lines += ["", "## Per eval", "", "| Skill | Eval | Condition | Passed | Failed | Errors | Subject stop |", "|---|---|---|---|---|---|---|"]
    for r in rows_eval:
        lines.append(f"| {r['skill']} | {r['eval_id']} | {r['condition']} | {r['passed']} | {r['failed']} | {r['error']} | {r['subject_stop'] or ''} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"skills: {len(per_skill)}  pack with {pct(pack['with']['rate'])} without {pct(pack['without']['rate'])}  errors {pack['with']['error']}/{pack['without']['error']}")
    for skill, s in sorted(per_skill.items(), key=lambda kv: -(kv[1]["lift_points"] or -999)):
        print(f"  {skill:28s} with {pct(s['with_rate']):>6s}  without {pct(s['without_rate']):>6s}  lift {s['lift_points']}")


if __name__ == "__main__":
    main(sys.argv[1:])
