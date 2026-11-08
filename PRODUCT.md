# fintech-skills product brief

Read this before you make a product decision on fintech-skills without asking a person. It says
what the repository is for, who uses it, the rules every change keeps, what only a person may
decide, and how to choose when goals conflict.

Last reviewed 2026-11-07.

## What fintech-skills is

A public, MIT-licensed pack of Agent Skills that teach coding agents (Claude Code, Codex, Cursor,
Copilot, any agent that reads `SKILL.md`) how to handle money the way production fintech systems
do. Twelve skills at v0: money arithmetic, double-entry ledger, idempotent payments, webhook
handling, reconciliation, accounting sync, transaction classification, PII and card data, audit
trail, interest and amortization, Brazil payment rails, money tests.

Each skill is a folder with `SKILL.md` and `evals/evals.json`. Every skill also ships
`evals/vectors/`: a pytest file with a reference implementation, runnable against any
implementation through an environment variable.

## Who it serves

- The engineer who points a coding agent at payment, ledger or accounting code and wants the
  agent to make the choices a senior fintech engineer would make, with tests.
- The reviewer of that change, who uses the skill's checklist.
- The skill author, who needs to know whether a skill changes agent behavior, measured.

## Where we are going

1. v0 (done): twelve skills, evals in the skill-creator format, twelve vector suites, CI.
2. Measured: an eval runner that executes every eval prompt with and without the skill in a
   fresh agent session, grades the expectations, and records results per run with the model,
   the pass rates, tokens and duration. Results are published in the repository.
3. Portable: TypeScript ports of the vectors; skills listed in the public marketplaces.
4. Adopted: issues and pull requests from people outside the author's companies, and skills
   improved from their corrections.

## Rules that hold for every change

1. **Every rule is testable.** A rule that cannot be tested is rewritten or removed.
2. **Measured over claimed.** A statement about what a skill achieves names the run, the model
   and the number. No adjectives in place of measurements.
3. **Engineering practice, not advice.** No tax rates, statutory rounding, legal conclusions or
   investment guidance. Where a rule depends on a jurisdiction, the skill says so and keeps the
   engineering part.
4. **No vendor API documentation inside a skill.** Vendors ship their own plugins; skills link to
   them and cover the invariants vendors do not.
5. **No real data.** No customer data, account numbers, card numbers, document numbers or
   production logs in skills, evals, vectors, fixtures or results. Synthetic values only.
6. **Vectors are frozen.** Changing a vector or a reference implementation is a reviewed change
   with a reason. A new vector needs a reference that satisfies it.
7. **Evals never run in CI.** CI validates frontmatter and runs vectors. Eval runs cost model
   sessions and are started by a person or by an approved task, with the budget stated first.
8. **Results are append-only.** A run writes a new folder under `evals/results/`; nothing
   rewrites a previous run.
9. **Plain English, short sentences, tables for comparisons.** Portuguese README kept in sync
   for user-facing changes.
10. **Minimal dependencies.** Python standard library plus `pyyaml` and `pytest`. A new
    dependency is a person's decision.

## Never, unless a person changes this brief

- Changing a skill's rules or facts (what a skill tells an agent to do). The Owner may approve
  eval tooling, tests, layout and documentation; the substance of a skill is the author's.
- Removing a skill, renaming a skill, or changing the license.
- Publishing: making the repository public, posting, submitting to a marketplace, opening
  issues or pull requests on other repositories.
- Starting an eval run above the default budget (section "Eval defaults") or on a model other
  than the defaults.
- Adding a dependency, a network call beyond the agent CLI, or any credential.

## Eval defaults

- Subject model `claude-sonnet-5-5`; grader model `claude-sonnet-5-5`; one run per prompt per
  condition (with the skill, without the skill). Above that is a person's decision.
- A run records: run id, date, subject and grader models, skill, eval id, condition, verdict per
  expectation with evidence, pass rate, tokens, wall time, and the git sha of the skills.
- Results live under `evals/results/<run-id>/` with a `summary.md`. Nothing posts them anywhere.

## Who decides what

- The author (Felipe) decides the substance of every skill, the license, publishing and launch,
  and anything in the "Never" list.
- The Owner model decides, inside this brief: eval runner design, file layout, test strategy,
  grading method, naming, documentation structure, and which of two correct technical options
  to take.
- Engineering decides build order and technical approach, inside the rules above.
- When this brief, the README and the code say nothing about a question, do not invent the
  answer. Recommend one, give the reason and ask.

## When goals conflict

Keep a rule correct over keeping it broad. Prefer the measured claim over the better-sounding one.
Between two correct options take the smaller one that a reader can verify. A skill that says less
and is right beats a skill that says more.

## Terms

- **Skill**: a folder with `SKILL.md` an agent loads on demand.
- **Eval**: one prompt plus expectations a grader checks in the agent's transcript.
- **Expectation**: a verifiable statement about the transcript or the files the agent produced.
- **Vector**: a test case with known inputs and outputs, runnable against any implementation.
- **Reference implementation**: code that satisfies the vectors, proving they are consistent.
- **Condition**: with the skill installed in the session, or without it.
- **Subject model**: the model whose behavior the eval measures. **Grader**: the model or code
  that judges expectations.
- **Run**: one execution of the evals, with its own id and results folder.
