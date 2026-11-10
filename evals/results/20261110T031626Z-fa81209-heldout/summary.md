# Evaluation results, held-out run 20261110T031626Z-fa81209-heldout

Date 2026-11-10, started 03:16 UTC. Subject model `claude-fable-5-2`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless. Prompt set: **held-out** (`evals/heldout/<skill>.json`, two prompts per skill, never read when editing a skill). Effort `xhigh` for both roles. Thinking tokens were 73.5% of the subject's output tokens with the skill and 69.6% without.

**With the skill installed, 87.6% of expectations passed (92 of 105). Without it, 35.2% (37 of 105). Lift: 52.4 points.** 13 skills, 2 prompts each, one run per prompt per condition: 52 subject sessions, 52 grader sessions, 0 grader errors, 0 max-turn stops.

## Why this folder exists

The development prompts in `skills/*/evals/evals.json` were used to revise the skills after each run, so their number is in-sample. The held-out prompts were written on 2026-11-08 before any held-out run and are not read when a skill is edited; a held-out prompt changes only to fix a defect in the prompt itself, stated in the next run's summary. There is no development-prompt run for `claude-fable-5-2` yet; this held-out run is the only number for that model. It uses the same skills commit, runner, install rule, blinded grader and session flags as the development runs of the other models on this commit, which the README lists.

A first attempt at this run (`20261109T214153Z-fa81209-heldout`, 2026-11-09 21:42 to 2026-11-10 03:15 UTC) is not published: the runner's 900-second session timeout cut 6 of the 26 with-skill sessions before they finished, each scored 0, while no without-skill session came within 350 seconds of the limit. That attempt scored 65.7% with the skill against 36.2% without. `claude-fable-5-2` at effort `xhigh` spends about four times the wall time and output tokens of `claude-opus-5-5` on the same prompts, so this run raised the timeout to 2400 seconds and changed nothing else; its longest session took 1454 seconds.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 87.6% | 92 | 13 | 7,378,333 | 8,800,663 | 16798 |
| without | 35.2% | 37 | 68 | 1,860,751 | 2,512,787 | 4770 |

## Per skill

| Skill | With | Without | Lift (points) | Expectations per condition |
|---|---|---|---|---|
| brazil-payment-rails | 100.0% | 0.0% | 100.0 | 8 |
| webhook-handling | 100.0% | 22.2% | 77.8 | 9 |
| transaction-classification | 100.0% | 25.0% | 75.0 | 8 |
| double-entry-ledger | 100.0% | 37.5% | 62.5 | 8 |
| reconciliation | 87.5% | 25.0% | 62.5 | 8 |
| accounting-sync | 87.5% | 37.5% | 50.0 | 8 |
| audit-trail | 87.5% | 37.5% | 50.0 | 8 |
| idempotent-payments | 75.0% | 25.0% | 50.0 | 8 |
| money-tests | 50.0% | 0.0% | 50.0 | 8 |
| interest-and-amortization | 75.0% | 37.5% | 37.5 | 8 |
| money-arithmetic | 100.0% | 62.5% | 37.5 | 8 |
| fintech-audit | 100.0% | 87.5% | 12.5 | 8 |
| pii-and-card-data | 75.0% | 62.5% | 12.5 | 8 |

## Reading the numbers

- Two prompts per skill: a per-skill cell has 6 to 9 expectations, so per-skill numbers here are indicative only; the pack-level number over 105 expectations per condition is the one to quote beside the development number.
- In 0 of 26 with-condition sessions the agent never opened the skill (none).
- Evals lower with the skill by two or more expectations: none; by one: none.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 4/4 | 2/4 | yes |
| accounting-sync | 2 | 3/4 | 1/4 | yes |
| audit-trail | 1 | 3/4 | 0/4 | yes |
| audit-trail | 2 | 4/4 | 3/4 | yes |
| brazil-payment-rails | 1 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 2 | 4/4 | 0/4 | yes |
| double-entry-ledger | 1 | 4/4 | 2/4 | yes |
| double-entry-ledger | 2 | 4/4 | 1/4 | yes |
| fintech-audit | 1 | 4/4 | 3/4 | yes |
| fintech-audit | 2 | 4/4 | 4/4 | yes |
| idempotent-payments | 1 | 2/4 | 1/4 | yes |
| idempotent-payments | 2 | 4/4 | 1/4 | yes |
| interest-and-amortization | 1 | 2/4 | 1/4 | yes |
| interest-and-amortization | 2 | 4/4 | 2/4 | yes |
| money-arithmetic | 1 | 4/4 | 3/4 | yes |
| money-arithmetic | 2 | 4/4 | 2/4 | yes |
| money-tests | 1 | 3/4 | 0/4 | yes |
| money-tests | 2 | 1/4 | 0/4 | yes |
| pii-and-card-data | 1 | 4/4 | 4/4 | yes |
| pii-and-card-data | 2 | 2/4 | 1/4 | yes |
| reconciliation | 1 | 4/4 | 2/4 | yes |
| reconciliation | 2 | 3/4 | 0/4 | yes |
| transaction-classification | 1 | 4/4 | 1/4 | yes |
| transaction-classification | 2 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 1/5 | yes |
| webhook-handling | 2 | 4/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields.
- `skills/<skill>.json`: one record per (eval, condition) with the exact `claude` invocation, final answer, tokens, files written with sha256, and the grader's verdict and evidence per expectation.
- `raw-20261110T031626Z-fa81209-heldout.tar.gz`, attached to the GitHub release: subject and grader transcripts and the files the subject wrote.
