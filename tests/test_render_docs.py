"""The README blocks quote one run per subject model on the latest skills commit, and the docs check
renders against the runs the README already names, so a results folder can land before the README does."""
from scripts import render_docs as rd

SKILLS = [p.name for p in rd.skills_in_order()]


def fake_run(run_id, model, with_rate, without_rate, not_opened=(), n=28, kind="dev"):
    sha = run_id.split("-")[1]
    skills = {}
    for i, name in enumerate(SKILLS):
        w = round(with_rate * n) - (i % 2)
        wo = round(without_rate * n) + (i % 3)
        skills[name] = {"with": {"passed": w, "failed": n - w}, "without": {"passed": wo, "failed": n - wo},
                        "with_rate": w / n, "without_rate": wo / n, "lift_points": round((w - wo) / n * 100, 1)}
    total = n * len(SKILLS)
    pw, pwo = round(with_rate * total), round(without_rate * total)
    return {"id": run_id, "sha": sha, "kind": kind, "meta": {"subject_model": model, "grader_model": "claude-sonnet-5-5"},
            "pack": {"with": {"rate": pw / total, "passed": pw, "failed": total - pw}, "without": {"rate": pwo / total, "passed": pwo, "failed": total - pwo}},
            "skills": skills, "evals": [{"condition": "with"}] * (7 * len(SKILLS)) + [{"condition": "without"}] * (7 * len(SKILLS)),
            "method": {"skill_not_opened_with": list(not_opened)}}


OLD = fake_run("20261108T143507Z-ae8adc1", "claude-sonnet-5-5", 0.78, 0.26)
SONNET = fake_run("20261108T180307Z-fa81209", "claude-sonnet-5-5", 0.81, 0.24, not_opened=["accounting-sync/4"])
OPUS = fake_run("20261109T103432Z-fa81209", "claude-opus-5-5", 0.89, 0.35)
RUNS = [OLD, SONNET, OPUS]


def test_models_on_commit_keeps_first_measured_order_and_only_the_latest_sha():
    per_model = rd.models_on_commit(OPUS, RUNS)
    assert list(per_model) == ["claude-sonnet-5-5", "claude-opus-5-5"]
    assert per_model["claude-sonnet-5-5"]["id"] == SONNET["id"]


def test_skills_table_has_one_named_column_per_model():
    table = rd.skills_table("en", OPUS, RUNS)
    head, sep, first = table.split("\n")[:3]
    assert head == "| Skill | Use when | `claude-sonnet-5-5` with / without | `claude-opus-5-5` with / without | Vectors |"
    assert sep == "|---|---|---|---|---|"
    assert first.count(" / ") == 2 and first.count("|") == 6
    assert "carries up to about ±" in table
    pt = rd.skills_table("pt", OPUS, RUNS).split("\n")[0]
    assert "`claude-sonnet-5-5` com / sem | `claude-opus-5-5` com / sem" in pt


def test_skills_table_with_one_model_names_it_and_drops_up_to():
    table = rd.skills_table("en", SONNET, [OLD, SONNET])
    assert table.split("\n")[0] == "| Skill | Use when | `claude-sonnet-5-5` with / without | Vectors |"
    assert "carries about ±" in table and "up to" not in table


def test_cut_rule_and_runs_block_name_each_model():
    rule = rd.cut_rule("en", OPUS, RUNS)
    assert "In the `claude-sonnet-5-5` run on `fa81209` the lowest lift was" in rule
    assert "; in the `claude-opus-5-5` run on `fa81209` the lowest lift was" in rule
    assert "latest run" not in rule
    block = rd.runs_block("en", RUNS)
    assert "In 1 of the 91 with-skill sessions of the `claude-sonnet-5-5` run on `fa81209` the agent never opened the skill; that session counts against the skills." in block
    assert "In all 91 with-skill sessions of the `claude-opus-5-5` run on `fa81209` the agent opened the skill." in block
    assert block.count("| `claude-") == 3  # one table row per run, every run listed


def test_named_runs_reads_dev_and_heldout_ids():
    text = ("see [evals/results/20261108T180307Z-fa81209](evals/results/20261108T180307Z-fa81209/summary.md) and "
            "[x](evals/results/20261108T194552Z-fa81209-heldout/summary.md)")
    assert rd.named_runs(text) == {"20261108T180307Z-fa81209", "20261108T194552Z-fa81209-heldout"}
    assert rd.named_runs("no links here") == set()


FABLE_HELDOUT = fake_run("20261110T031626Z-fa81209-heldout", "claude-fable-5-2", 0.88, 0.35, n=8, kind="heldout")


def test_model_with_only_a_heldout_run_gets_a_labelled_column_and_its_own_note():
    table = rd.skills_table("en", OPUS, RUNS + [FABLE_HELDOUT])
    head = table.split("\n")[0]
    assert head.endswith("| `claude-opus-5-5` with / without | `claude-fable-5-2` with / without, held-out | Vectors |")
    assert table.split("\n")[2].count(" / ") == 3
    assert "The `claude-fable-5-2` column is its held-out run (two prompts per skill, cells of about 8 expectations" in table
    assert "read it at the pack level: 88% with, 35% without." in table
    assert "claude-fable-5-2" not in rd.cut_rule("en", OPUS, RUNS + [FABLE_HELDOUT])  # dev runs only
    pt = rd.skills_table("pt", OPUS, RUNS + [FABLE_HELDOUT])
    assert "`claude-fable-5-2` com / sem, reservado" in pt.split("\n")[0]
