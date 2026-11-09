# Evaluation results, held-out run 20261109T110030Z-fa81209-heldout

Date 2026-11-09, started 11:00 UTC. Subject model `claude-opus-5-5`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless. Prompt set: **held-out** (`evals/heldout/<skill>.json`, two prompts per skill, never read when editing a skill).

**With the skill installed, 81.0% of expectations passed (85 of 105). Without it, 31.4% (33 of 105). Lift: 49.5 points.** 13 skills, 2 prompts each, one run per prompt per condition: 52 subject sessions, 52 grader sessions, 0 grader errors, 0 max-turn stops.

## Why this folder exists

The development prompts in `skills/*/evals/evals.json` were used to revise the skills after each run, so their number is in-sample. The held-out prompts were written on 2026-11-08 before any held-out run and are not read when a skill is edited; a held-out prompt changes only to fix a defect in the prompt itself, stated in the next run's summary. This run measures the same skills commit as the development run [20261109T103432Z-fa81209](../20261109T103432Z-fa81209/summary.md), with the same runner, install rule, blinded grader and session flags; only the prompt set differs.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 81.0% | 85 | 20 | 4,312,870 | 3,391,460 | 5164 |
| without | 31.4% | 33 | 72 | 799,501 | 744,741 | 1124 |

## Per skill

| Skill | With | Without | Lift (points) | Expectations per condition |
|---|---|---|---|---|
| brazil-payment-rails | 100.0% | 0.0% | 100.0 | 8 |
| transaction-classification | 100.0% | 25.0% | 75.0 | 8 |
| accounting-sync | 100.0% | 37.5% | 62.5 | 8 |
| idempotent-payments | 75.0% | 12.5% | 62.5 | 8 |
| pii-and-card-data | 75.0% | 12.5% | 62.5 | 8 |
| webhook-handling | 66.7% | 11.1% | 55.6 | 9 |
| audit-trail | 87.5% | 37.5% | 50.0 | 8 |
| money-tests | 62.5% | 12.5% | 50.0 | 8 |
| double-entry-ledger | 75.0% | 37.5% | 37.5 | 8 |
| money-arithmetic | 100.0% | 62.5% | 37.5 | 8 |
| interest-and-amortization | 75.0% | 50.0% | 25.0 | 8 |
| fintech-audit | 87.5% | 75.0% | 12.5 | 8 |
| reconciliation | 50.0% | 37.5% | 12.5 | 8 |

## Reading the numbers

- Two prompts per skill: a per-skill cell has 6 to 9 expectations, so per-skill numbers here are indicative only; the pack-level number over 105 expectations per condition is the one to quote beside the development number.
- In 1 of 26 with-condition sessions the agent never opened the skill (fintech-audit eval 2).
- Evals lower with the skill by two or more expectations: none; by one: none.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 4/4 | 0/4 | yes |
| accounting-sync | 2 | 4/4 | 3/4 | yes |
| audit-trail | 1 | 3/4 | 1/4 | yes |
| audit-trail | 2 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 2 | 4/4 | 0/4 | yes |
| double-entry-ledger | 1 | 4/4 | 2/4 | yes |
| double-entry-ledger | 2 | 2/4 | 1/4 | yes |
| fintech-audit | 1 | 4/4 | 3/4 | yes |
| fintech-audit | 2 | 3/4 | 3/4 | no |
| idempotent-payments | 1 | 2/4 | 0/4 | yes |
| idempotent-payments | 2 | 4/4 | 1/4 | yes |
| interest-and-amortization | 1 | 2/4 | 2/4 | yes |
| interest-and-amortization | 2 | 4/4 | 2/4 | yes |
| money-arithmetic | 1 | 4/4 | 3/4 | yes |
| money-arithmetic | 2 | 4/4 | 2/4 | yes |
| money-tests | 1 | 3/4 | 0/4 | yes |
| money-tests | 2 | 2/4 | 1/4 | yes |
| pii-and-card-data | 1 | 4/4 | 0/4 | yes |
| pii-and-card-data | 2 | 2/4 | 1/4 | yes |
| reconciliation | 1 | 4/4 | 3/4 | yes |
| reconciliation | 2 | 0/4 | 0/4 | yes |
| transaction-classification | 1 | 4/4 | 1/4 | yes |
| transaction-classification | 2 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 0/5 | yes |
| webhook-handling | 2 | 1/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields.
- `skills/<skill>.json`: one record per (eval, condition) with the exact `claude` invocation, final answer, tokens, files written with sha256, and the grader's verdict and evidence per expectation.
- `raw-20261109T110030Z-fa81209-heldout.tar.gz`, attached to the GitHub release: subject and grader transcripts and the files the subject wrote.
