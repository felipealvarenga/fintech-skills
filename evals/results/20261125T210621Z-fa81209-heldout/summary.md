# Evaluation results, held-out run 20261125T210621Z-fa81209-heldout

Date 2026-11-25, started 21:06 UTC. Subject model `gemini-4-neon-high` via Antigravity CLI (`agy` 1.5.17, headless). Grader model `claude-sonnet-5-5` (2.1.332 (Claude Code), headless, effort `xhigh`). Prompt set: **held-out** (`evals/heldout/<skill>.json`, two prompts per skill, never read when editing a skill). Thinking tokens were 43.3% of the subject's output tokens with the skill and 55.9% without.

**With the skill installed, 85.7% of expectations passed (90 of 105). Without it, 36.2% (38 of 105). Lift: 49.5 points.** 13 skills, 2 prompts each, one run per prompt per condition: 52 subject sessions, 52 grader sessions, 0 grader errors, 0 max-turn stops.

## Why this folder exists

The development prompts in `skills/*/evals/evals.json` were used to revise the skills after each run, so their number is in-sample. The held-out prompts were written on 2026-11-08 before any held-out run and are not read when a skill is edited. This run measures the same skills text (`fa81209`, checkout `24568b6`) as the development run [20261125T151436Z-fa81209](../20261125T151436Z-fa81209/summary.md), with the same `agy` isolation, install rule and blinded `claude-sonnet-5-5` grader; only the prompt set differs.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 85.7% | 90 | 15 | 10,548,365 | 1,476,092 | 11309 |
| without | 36.2% | 38 | 67 | 2,391,784 | 456,512 | 3392 |

## Per skill

| Skill | With | Without | Lift (points) | Expectations per condition |
|---|---|---|---|---|
| webhook-handling | 100.0% | 11.1% | 88.9 | 9 |
| brazil-payment-rails | 100.0% | 12.5% | 87.5 | 8 |
| idempotent-payments | 75.0% | 12.5% | 62.5 | 8 |
| money-tests | 75.0% | 12.5% | 62.5 | 8 |
| transaction-classification | 100.0% | 37.5% | 62.5 | 8 |
| accounting-sync | 87.5% | 37.5% | 50.0 | 8 |
| interest-and-amortization | 75.0% | 25.0% | 50.0 | 8 |
| pii-and-card-data | 62.5% | 12.5% | 50.0 | 8 |
| fintech-audit | 100.0% | 62.5% | 37.5 | 8 |
| audit-trail | 87.5% | 62.5% | 25.0 | 8 |
| double-entry-ledger | 87.5% | 62.5% | 25.0 | 8 |
| money-arithmetic | 100.0% | 75.0% | 25.0 | 8 |
| reconciliation | 62.5% | 50.0% | 12.5 | 8 |

## Reading the numbers

- Two prompts per skill: a per-skill cell has 8 to 9 expectations, so per-skill numbers here are indicative only; the pack-level number over 105 expectations per condition is the one to quote beside the development number.
- In 0 of 26 with-condition sessions the agent never opened the skill (none).
- Evals lower with the skill by two or more expectations: none; by one: none.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 3/4 | 0/4 | yes |
| accounting-sync | 2 | 4/4 | 3/4 | yes |
| audit-trail | 1 | 3/4 | 3/4 | yes |
| audit-trail | 2 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 2 | 4/4 | 1/4 | yes |
| double-entry-ledger | 1 | 4/4 | 3/4 | yes |
| double-entry-ledger | 2 | 3/4 | 2/4 | yes |
| fintech-audit | 1 | 4/4 | 2/4 | yes |
| fintech-audit | 2 | 4/4 | 3/4 | yes |
| idempotent-payments | 1 | 2/4 | 0/4 | yes |
| idempotent-payments | 2 | 4/4 | 1/4 | yes |
| interest-and-amortization | 1 | 2/4 | 0/4 | yes |
| interest-and-amortization | 2 | 4/4 | 2/4 | yes |
| money-arithmetic | 1 | 4/4 | 4/4 | yes |
| money-arithmetic | 2 | 4/4 | 2/4 | yes |
| money-tests | 1 | 4/4 | 0/4 | yes |
| money-tests | 2 | 2/4 | 1/4 | yes |
| pii-and-card-data | 1 | 3/4 | 0/4 | yes |
| pii-and-card-data | 2 | 2/4 | 1/4 | yes |
| reconciliation | 1 | 3/4 | 3/4 | yes |
| reconciliation | 2 | 2/4 | 1/4 | yes |
| transaction-classification | 1 | 4/4 | 2/4 | yes |
| transaction-classification | 2 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 0/5 | yes |
| webhook-handling | 2 | 4/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields.
- `skills/<skill>.json`: one record per (eval, condition) with the `agy` subject invocation, final answer, tokens, files written with sha256, and the `claude-sonnet-5-5` grader's verdict and evidence per expectation.
- `raw-20261125T210621Z-fa81209-heldout.tar.gz`: subject and grader transcripts and produced files.
