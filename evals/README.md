# Evals

Every skill has `evals/evals.json` in the format used by Anthropic's `skill-creator`
(`skill_name`, `evals[]` with `id`, `prompt`, `expected_output`, `expectations`). From the repository
root, run paired evaluations with the local Claude Code CLI and its existing login:

```sh
python3 scripts/run_evals.py --skill money-arithmetic
python3 scripts/run_evals.py --skill money-arithmetic --skill money-tests
python3 scripts/run_evals.py --all --budget 144
python3 scripts/run_evals.py --skill money-arithmetic --agent fake --results-dir /tmp/skill-evals
```

Evals never run in CI. A person starts a real run and approves its budget. The pytest suite uses
in-process fake agents, not Claude. Fake results measure the runner, not a skill's quality.

| Flag | Default | Meaning |
|---|---|---|
| `--skill NAME` | none | Select a skill; repeat for several skills. |
| `--all` | off | Select all skills. Required instead of `--skill`, never together. |
| `--subject-model` | `claude-sonnet-5-5` | Subject model. |
| `--grader-model` | `claude-sonnet-5-5` | Grader model. |
| `--runs` | `1` | Repetitions per prompt and condition. |
| `--max-turns` | `30` | Subject turn limit. Partial output is still graded. |
| `--timeout` | `900` | Seconds per subject or grader session; timed-out processes are killed. |
| `--budget` | `80` | Maximum planned sessions, including graders. |
| `--results-dir` | `evals/results` | Parent of the new append-only run folder; default is relative to the repository root. |
| `--agent` | `claude` | `claude` or deterministic, in-process `fake`. |
| `--help` | off | Show CLI help. |

The plan prints before any session or result write. Total sessions = prompts × 2 conditions ×
runs × 2 roles (subject and grader). All 36 prompts plan 72 subjects and 72 graders: 144 sessions,
so the default budget refuses a full run. One skill plans 12 sessions. Errors may reduce the
started count. Sessions run sequentially, with no retries or resume.

Each subject gets a new temporary project outside the repository. Input `files` are relative to
the skill folder and copied at the same relative path. Absolute paths, `..` segments and missing
files become prompt errors. Only the with condition installs `.claude/skills/<name>/`: the skill
folder minus `evals/evals.json` and local `__pycache__` artifacts. `SKILL.md` and any vectors stay
installed. Both conditions get Read, Write, Edit, Glob, Grep and Skill, with project-only settings, strict MCP configuration and
no session persistence. Both subject and grader inherit the environment with
`CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` to disable `CLAUDE.md` discovery. No Bash, web or Agent tool is
enabled. The runner adds no credential.

A separate grader gets an empty temporary project, no tools, and the prompt, expectations,
answer, full transcript and produced files. It is not given the condition label or storage
paths. It returns ordered boolean verdicts with evidence. Static checks require a produced test
file when an expectation asks for tests, and a produced named path when a backticked path is
specified. Both grader and code checks must pass. Produced code is never executed.

Subject timeouts or non-zero exits are errors for all affected expectations. Invalid grader JSON
is also an error; missing or malformed individual verdicts affect only those expectations.
Pass rate = passed / (passed + failed), excluding errors; no grades means `n/a`. Max-turns stops
are counted separately. Fake mode uses both model labels `fake` and marks the summary's first
line. It starts no agent processes; Git commands still read the repository's SHA and dirty state.

## Results

```text
evals/results/<UTC YYYYMMDDTHHMMSSZ>-<7-character git sha>/
  summary.md
  <skill>.json
  raw/<skill>/<eval-id>-<with|without>-<run>/
    subject-transcript.txt
    subject-stderr.txt
    grader-transcript.txt
    grader-stderr.txt
    grader-stdin.json
    files.json
    files/<produced-path>
```

An existing run folder is refused, never overwritten. Skill JSON holds metadata, installed paths,
each answer, verdicts and evidence, static checks, exact CLI invocations, separate subject/grader
tokens and wall time, and raw item paths. The summary shows per-skill and all-skills condition
rows, planned and started sessions, and the total raw size. Git state includes uncommitted changes
under `skills/`. Temporary projects are removed after capture, including on errors and timeouts.

Created or changed files outside `.claude/` are captured. A produced file over 256 KB gets only
its name, size and SHA-256. Smaller files keep their bytes under `files/`; manifests hold only
metadata and raw paths. The raw grader stdin includes file contents (base64 for binary files)
and the whole transcript. Stored text replaces the temporary project path with `<project>`.
Results are not gitignored; review their size and contents before choosing whether to commit them.

## Vectors

Four skills also ship **vectors**: language-neutral test cases as pytest files with a reference
implementation that proves they are satisfiable.

| Skill | Vectors | Environment variable |
|---|---|---|
| money-arithmetic | `skills/money-arithmetic/evals/vectors/test_money.py` | `MONEY_SOLUTION` |
| double-entry-ledger | `skills/double-entry-ledger/evals/vectors/test_ledger.py` | `LEDGER_SOLUTION` |
| interest-and-amortization | `skills/interest-and-amortization/evals/vectors/test_amortization.py` | `AMORT_SOLUTION` |
| reconciliation | `skills/reconciliation/evals/vectors/test_reconcile.py` | `RECON_SOLUTION` |

```sh
python -m pytest -q skills                                   # all vectors against the references
MONEY_SOLUTION=./src/money.py python -m pytest -q skills/money-arithmetic   # your implementation
```

The vectors are Python today. The cases are listed in each test file so they can be ported to
another language by hand.
