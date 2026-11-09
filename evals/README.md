# Evals

Every skill has `evals/evals.json` in the format used by Anthropic's `skill-creator`
(`skill_name`, `evals[]` with `id`, `prompt`, `expected_output`, `expectations`). From the repository
root, run paired evaluations with the local Claude Code CLI and its existing login:

```sh
python3 scripts/run_evals.py --skill money-arithmetic
python3 scripts/run_evals.py --skill money-arithmetic --skill money-tests
python3 scripts/run_evals.py --all --budget 364
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
runs × 2 roles (subject and grader). All 91 prompts plan 182 subjects and 182 graders: 364 sessions,
so the default budget refuses a full run. One skill plans 28 sessions. Errors may reduce the
started count. Sessions run sequentially, with no retries or resume.

Each subject gets a new temporary project outside the repository. Input `files` are relative to
the skill folder: `evals/files/<file>` goes to `src/<file>`, while
`evals/files/<fixture>/<rest>` goes to `<rest>` at the project root. Entries outside
`evals/files/`, absolute paths, `..` segments, missing files and duplicate targets become prompt
errors before its session starts. Only the with condition installs `.claude/skills/<name>/`:
the skill folder without anything under `evals/` and without local `__pycache__` artifacts.
`SKILL.md`, `scripts/` and `references/` are installed; `evals.json`, `evals/files/`,
`evals/vectors/` (the reference implementations would leak the answers) and `sample-report.md`
are not. For `fintech-audit` only, the with condition installs
all 13 skill folders using the same rule: it measures the entry point with its pack. Every other
skill installs alone; the without condition installs nothing under `.claude/`.
Both conditions get Read, Write, Edit, Glob, Grep and Skill, with project-only settings, strict MCP configuration and
no session persistence. Both subject and grader run with an allowlisted environment (`HOME`, `PATH`, locale,
`XDG_*` and `TMPDIR`, `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_*`), plus
`CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` to disable `CLAUDE.md` discovery and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`
to keep Claude Code's bundled skills out of the session. Nothing else from the operator's shell reaches a
session. No Bash, web or Agent tool is enabled. The runner adds no credential.

The fintech-audit eval 3 expectation "Runs the lint and reports zero leads" and eval 4 expectation
"Runs the lint despite the request and says why in one sentence" are expected to fail in both
conditions until a sandboxed Bash exists. They are graded normally, not excluded from pass rates.

A separate grader gets an empty temporary project, no tools, and the prompt, expectations,
answer, transcript and produced files. Before the transcript reaches it, the runner removes the
installed-skill list from the session header, the `Skill` tool calls and every read of a file under
`.claude/skills/` with their results, so the condition is not shown to it; the subject's own prose
can still name the skill, which is reported, not hidden. Storage paths are not sent. Grader and
subject are the same model unless `--grader-model` says otherwise. It returns ordered boolean
verdicts with evidence. Static checks require a produced test
file when an expectation asks for tests, and a produced named path when a backticked path is
specified. Both grader and code checks must pass. Produced code is never executed.

Subject timeouts or non-zero exits are errors for all affected expectations. Invalid grader JSON
is also an error; missing or malformed individual verdicts affect only those expectations.
Pass rate = passed / (passed + failed), excluding errors; no grades means `n/a`. Max-turns stops
are counted separately. Fake mode uses both model labels `fake` and marks the summary's first
line. It starts no agent processes; Git commands still read the repository's SHA and dirty state.

## Held-out set

`evals/heldout/<skill>.json` holds two prompts per skill that are never read when editing a skill
(fixtures under `evals/heldout/files/<skill>/`). They exist so one number is out of sample: the
development prompts in `skills/*/evals/evals.json` were used to revise the skills, the held-out
prompts were not. `python3 scripts/run_evals.py --all --evals heldout --budget 104` runs them into a
folder named `<timestamp>-<sha>-heldout`; the README shows the held-out number beside the
development one for the same commit. A held-out prompt changes only to fix a defect in the prompt
itself, stated in the next run's summary.

## Noise rule

One run per prompt per condition. An eval counts as lower with the skill than without only when it
drops by two or more expectations; a one-expectation drop triggers one re-run of that skill, and
both results are reported. Per-cell numbers (about 28 expectations) carry about ±16 points at 95%;
the pack-level numbers about ±5.

## Results

A run writes one folder, refused if it exists:

```text
evals/results/<UTC YYYYMMDDTHHMMSSZ>-<7-character git sha>/
  summary.md                 the runner's tables
  <skill>.json               metadata, installed paths, each answer, verdicts with evidence, exact CLI invocations, tokens, wall time
  raw/<skill>/<eval-id>-<with|without>-<run>/
    subject-transcript.txt   grader-transcript.txt   grader-stdin.json   *-stderr.txt   files.json   files/<produced-path>
```

The committed form of a run is `summary.md`, `results.json` and `skills/<skill>.json`:
`python3 scripts/aggregate_results.py <run-dir> <out-dir>` writes `results.json` in the schema
`scripts/render_docs.py` reads (pack, per skill, per eval) and copies the skill files; the narrative
at the top of a committed `summary.md` is written by hand after reading the failures. `raw/`
(transcripts and produced files, about 10 MB per run) is not committed, so a plugin install stays
small; each run's `raw/` is attached to the GitHub release as `raw-<run-id>.tar.gz`. Stored text
replaces the temporary project path with `<project>` and machine paths with `<home>` and `<tmp>`.
Git state includes uncommitted changes under `skills/`. Temporary projects are removed after
capture, including on errors and timeouts. A produced file over 256 KB keeps only its name, size and
SHA-256.

## Vectors

Every skill also ships **vectors**: language-neutral test cases as pytest files with a reference
implementation that proves they are satisfiable. Point the environment variable at your own
module to run them against your code.

<!-- generated:vectors-table -->
| Skill | Python | TypeScript | Environment variable | Names your module must export |
|---|---|---|---|---|
| fintech-audit | `skills/fintech-audit/evals/vectors/test_lint.py` | none | `AUDIT_LINT` | see the file |
| money-arithmetic | `skills/money-arithmetic/evals/vectors/test_money.py` | `skills/money-arithmetic/evals/vectors/money.test.ts` | `MONEY_SOLUTION`, `MONEY_SOLUTION_TS` | `add`, `allocate`, `apply_rate`, `convert`, `from_minor`, `to_minor` |
| double-entry-ledger | `skills/double-entry-ledger/evals/vectors/test_ledger.py` | `skills/double-entry-ledger/evals/vectors/ledger.test.ts` | `LEDGER_SOLUTION`, `LEDGER_SOLUTION_TS` | `Entry`, `Ledger`, `Posting` |
| idempotent-payments | `skills/idempotent-payments/evals/vectors/test_idempotency.py` | `skills/idempotent-payments/evals/vectors/idempotency.test.ts` | `IDEMPOTENCY_SOLUTION`, `IDEMPOTENCY_SOLUTION_TS` | `FakeProcessor`, `FingerprintMismatch`, `IdempotencyStore`, `IllegalTransition`, `InProgress`, `PaymentService`, `RetryPolicy`, `is_retryable`, `transition` |
| webhook-handling | `skills/webhook-handling/evals/vectors/test_webhooks.py` | `skills/webhook-handling/evals/vectors/webhooks.test.ts` | `WEBHOOK_SOLUTION`, `WEBHOOK_SOLUTION_TS` | `BadSignature`, `EventStore`, `apply_state`, `receive`, `response_status`, `sign`, `verify` |
| reconciliation | `skills/reconciliation/evals/vectors/test_reconcile.py` | none | `RECON_SOLUTION` | `Line`, `reconcile` |
| accounting-sync | `skills/accounting-sync/evals/vectors/test_sync.py` | none | `SYNC_SOLUTION` | `FakeAccounting`, `PeriodClosed`, `Sync`, `TokenStore`, `drift_report` |
| transaction-classification | `skills/transaction-classification/evals/vectors/test_classification.py` | none | `CLASSIFY_SOLUTION` | `GatePolicy`, `InvalidOutput`, `Line`, `classify_with_layers`, `decide`, `normalize_merchant`, `pair_transfers`, `validate_output` |
| pii-and-card-data | `skills/pii-and-card-data/evals/vectors/test_pii.py` | none | `BRAZIL_SOLUTION`, `PII_SOLUTION` | `luhn_check_digit`, `luhn_valid`, `make_test_cpf`, `make_test_pan`, `mask_document`, `mask_pan`, `redact`, `scan`, `schema_lint` |
| audit-trail | `skills/audit-trail/evals/vectors/test_audit.py` | none | `AUDIT_SOLUTION` | `AuditError`, `AuditLog`, `mutate` |
| interest-and-amortization | `skills/interest-and-amortization/evals/vectors/test_amortization.py` | none | `AMORT_SOLUTION` | `effective_to_periodic`, `price_schedule`, `sac_schedule`, `simple_interest` |
| brazil-payment-rails | `skills/brazil-payment-rails/evals/vectors/test_brazil.py` | `skills/brazil-payment-rails/evals/vectors/brazil.test.ts` | `BRAZIL_SOLUTION`, `BRAZIL_SOLUTION_TS` | `barcode_from_typeable_line`, `build_barcode`, `cnpj_check_digits`, `due_date_from_factor`, `factor_from_due_date`, `format_cnpj`, `mask_cpf`, `mod10`, `mod11_barcode`, `normalize_cnpj`, `typeable_line`, `validate_barcode`, `validate_cnpj`, `validate_cpf` |
| money-tests | `skills/money-tests/evals/vectors/test_money_tests.py` | none | `MONEYTESTS_SOLUTION` | `kill_rate`, `lint_tests`, `meets_gate` |
<!-- /generated:vectors-table -->

Each suite imports the names in the last column from the module the environment variable points
at, so a production module usually needs an adapter of a few lines that exposes them. An import
or attribute error is an interface mismatch, not a money defect; a failing assertion is.

Each skill has seven evals: three build prompts, three judgment prompts and at least one
adversarial prompt that asks for the unsafe thing (keep the floats, disable the signature check,
mark the order paid on issuance). Prompts that imply existing code list fixture files under
`evals/files/`, copied into the temporary project as `src/` before the session starts; greenfield
prompts say so. Expectations are written to be gradable from the transcript and the produced
files.

```sh
python -m pytest -q skills                                   # all vectors against the references
MONEY_SOLUTION=./src/money.py python -m pytest -q skills/money-arithmetic   # your implementation
```

TypeScript ports live beside the Python files (`*.test.ts` with `reference.ts`) and run with
`npm ci && npm run test:ts`; point `MONEY_SOLUTION_TS` (and the matching variable per skill) at
your module. <!-- generated:ts-ports -->
TypeScript ports exist for money-arithmetic, double-entry-ledger, idempotent-payments, webhook-handling, brazil-payment-rails; fintech-audit, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, money-tests are Python only.
<!-- /generated:ts-ports -->
