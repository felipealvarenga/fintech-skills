# Evaluation results, run 20261109T103432Z-fa81209

Date 2026-11-09, 10:34 to 15:32 UTC. Subject model `claude-opus-5-5`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless. Development prompts (`skills/*/evals/evals.json`). Same skills commit, runner, prompts and grader as the `claude-sonnet-5-5` run [20261108T180307Z-fa81209](../20261108T180307Z-fa81209/summary.md); only the subject model differs.

**With the skill installed, 88.6% of expectations passed (328 of 370). Without it, 35.1% (130 of 370). Lift: 53.5 points.** 13 skills, 7 prompts each, one run per prompt per condition: 182 subject sessions, 182 grader sessions, 0 grader errors, 0 max-turn stops.

## Why a second subject model

The Sonnet run on this commit measures what the default Claude Code model does with and without the skills. Many of the engineers this pack is for run `claude-opus-5-5`; this run asks whether the skills still change what that model does, with the same grader (`claude-sonnet-5-5`) so the two runs are graded alike. Nothing in the skills, the prompts, the expectations or the runner differs from the Sonnet run. A first attempt at this run on 2026-11-08 was lost to a machine reboot after eight skills and is not published; this run started from scratch on 2026-11-09.

The Sonnet run measured 80.8% with and 23.5% without (299 and 87 of 370).

## Method

- Runner: `scripts/run_evals.py` from `main` at the time of the run (the install excludes everything under `evals/`; the grader transcript is blinded: the installed-skill list, the `Skill` calls and the reads under `.claude/skills/` are removed before grading). One invocation per skill, in this order: double-entry-ledger, brazil-payment-rails, fintech-audit, money-arithmetic, idempotent-payments, webhook-handling, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, money-tests, 10:34 to 15:32 UTC. This folder combines the 13 run directories.
- Skills measured: `fa81209`, the release candidate; `skills_dirty: false`, a clean checkout.
- Install: `SKILL.md`, `references/` and `scripts/` copied to `.claude/skills/<name>/` in a fresh temporary project; `installed_paths` in each `skills/<skill>.json` lists exactly what the subject could read. fintech-audit installs all 13 skills in the with condition.
- Subject session: `claude -p --output-format json --model claude-opus-5-5 --max-turns 30 --tools Read,Write,Edit,Glob,Grep,Skill --setting-sources project --strict-mcp-config --permission-mode acceptEdits --permission-prompts none --no-session-persistence`, with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`. No Bash, no web tools, no MCP servers.
- Grader session: `claude-sonnet-5-5`, no tools. It receives the prompt, the expectations, the subject's final answer, the blinded transcript and every file the subject wrote, and returns one verdict with evidence per expectation.
- Pass rate = passed expectations / (passed + failed). Each eval has 3 to 6 expectations; each skill has 27 to 30 per condition.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 88.6% | 328 | 42 | 10,992,131 | 9,935,446 | 14308 |
| without | 35.1% | 130 | 240 | 2,606,435 | 2,533,589 | 3558 |

## Per skill

| Skill | With | Without | Lift (points) | Sonnet run with / without | Expectations per condition |
|---|---|---|---|---|---|
| transaction-classification | 96.3% | 25.9% | 70.4 | 100.0% / 22.2% | 27 |
| idempotent-payments | 100.0% | 35.7% | 64.3 | 85.7% / 21.4% | 28 |
| reconciliation | 86.2% | 24.1% | 62.1 | 72.4% / 10.3% | 29 |
| webhook-handling | 86.2% | 27.6% | 58.6 | 86.2% / 6.9% | 29 |
| accounting-sync | 85.7% | 28.6% | 57.1 | 67.9% / 21.4% | 28 |
| brazil-payment-rails | 86.2% | 31.0% | 55.2 | 89.7% / 20.7% | 29 |
| double-entry-ledger | 92.9% | 39.3% | 53.6 | 82.1% / 25.0% | 28 |
| money-tests | 100.0% | 46.7% | 53.3 | 96.7% / 30.0% | 30 |
| audit-trail | 85.2% | 33.3% | 51.9 | 74.1% / 25.9% | 27 |
| interest-and-amortization | 78.6% | 32.1% | 46.4 | 71.4% / 17.9% | 28 |
| fintech-audit | 83.3% | 40.0% | 43.3 | 76.7% / 33.3% | 30 |
| money-arithmetic | 90.0% | 46.7% | 43.3 | 83.3% / 33.3% | 30 |
| pii-and-card-data | 81.5% | 44.4% | 37.0 | 63.0% / 37.0% | 27 |

webhook-handling eval 5 ("we trust Stripe, no API call"): with 0/4 here, 0/4 in the Sonnet run; without 0/4 and 0/4. brazil-payment-rails eval 4 ("keep the static QR, we match by payer name"): with 2/4 here, 2/4 in the Sonnet run.

## The release bar, applied to this model

The bar stated for the release applies to the Sonnet run; this run reports the same checks for the second model. One run per prompt per condition, so an eval counts as lower only when it drops by two or more expectations; a drop of one triggers one re-run of that skill, and both results are reported.

- brazil-payment-rails with the skill: 86.2%.
- Lowest lift: pii-and-card-data at 37.0 points.
- Evals lower with the skill by two or more expectations: none.
- Evals lower by one expectation: none.

## Reading the numbers

- The without condition here is the model's unaided baseline: 35.1% against Sonnet's 23.5% on the same prompts; the largest per-skill difference between the two models' baselines is 21 points (webhook-handling). The pack-level gap of 53.5 points over 370 expectations per condition is many times the run-to-run variation seen between Sonnet runs; with one run per prompt and expectations that are correlated within a response, no confidence interval is claimed.
- In 0 of 91 with-condition sessions the agent never opened the skill (none); the Sonnet run had 2 (accounting-sync eval 4, webhook-handling eval 5).
- The with condition used 4.2x the subject tokens of the without condition.
- The remaining with-condition failures are largest in interest-and-amortization (6) and fintech-audit (5).
- These are development prompts: the skills were revised against earlier runs' failures on them. The held-out set in `evals/heldout/` is measured for this model in its own folder on the same commit.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 5/5 | 1/5 | yes |
| accounting-sync | 2 | 4/4 | 2/4 | yes |
| accounting-sync | 3 | 2/3 | 2/3 | yes |
| accounting-sync | 4 | 3/4 | 0/4 | yes |
| accounting-sync | 5 | 4/4 | 1/4 | yes |
| accounting-sync | 6 | 2/4 | 1/4 | yes |
| accounting-sync | 7 | 4/4 | 1/4 | yes |
| audit-trail | 1 | 4/4 | 2/4 | yes |
| audit-trail | 2 | 4/4 | 1/4 | yes |
| audit-trail | 3 | 4/4 | 2/4 | yes |
| audit-trail | 4 | 2/4 | 1/4 | yes |
| audit-trail | 5 | 2/4 | 0/4 | yes |
| audit-trail | 6 | 3/3 | 1/3 | yes |
| audit-trail | 7 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 5/5 | 2/5 | yes |
| brazil-payment-rails | 2 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 3 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 4 | 2/4 | 0/4 | yes |
| brazil-payment-rails | 5 | 3/4 | 3/4 | yes |
| brazil-payment-rails | 6 | 3/4 | 1/4 | yes |
| brazil-payment-rails | 7 | 4/4 | 1/4 | yes |
| double-entry-ledger | 1 | 4/4 | 0/4 | yes |
| double-entry-ledger | 2 | 4/4 | 2/4 | yes |
| double-entry-ledger | 3 | 4/4 | 2/4 | yes |
| double-entry-ledger | 4 | 4/4 | 3/4 | yes |
| double-entry-ledger | 5 | 2/4 | 1/4 | yes |
| double-entry-ledger | 6 | 4/4 | 3/4 | yes |
| double-entry-ledger | 7 | 4/4 | 0/4 | yes |
| fintech-audit | 1 | 4/6 | 3/6 | yes |
| fintech-audit | 2 | 4/4 | 1/4 | yes |
| fintech-audit | 3 | 3/4 | 1/4 | yes |
| fintech-audit | 4 | 3/4 | 2/4 | yes |
| fintech-audit | 5 | 3/4 | 1/4 | yes |
| fintech-audit | 6 | 4/4 | 1/4 | yes |
| fintech-audit | 7 | 4/4 | 3/4 | yes |
| idempotent-payments | 1 | 5/5 | 1/5 | yes |
| idempotent-payments | 2 | 4/4 | 2/4 | yes |
| idempotent-payments | 3 | 4/4 | 3/4 | yes |
| idempotent-payments | 4 | 4/4 | 2/4 | yes |
| idempotent-payments | 5 | 4/4 | 1/4 | yes |
| idempotent-payments | 6 | 3/3 | 1/3 | yes |
| idempotent-payments | 7 | 4/4 | 0/4 | yes |
| interest-and-amortization | 1 | 5/5 | 3/5 | yes |
| interest-and-amortization | 2 | 2/3 | 1/3 | yes |
| interest-and-amortization | 3 | 3/4 | 1/4 | yes |
| interest-and-amortization | 4 | 2/4 | 1/4 | yes |
| interest-and-amortization | 5 | 4/4 | 2/4 | yes |
| interest-and-amortization | 6 | 3/4 | 0/4 | yes |
| interest-and-amortization | 7 | 3/4 | 1/4 | yes |
| money-arithmetic | 1 | 5/5 | 4/5 | yes |
| money-arithmetic | 2 | 4/4 | 3/4 | yes |
| money-arithmetic | 3 | 5/5 | 0/5 | yes |
| money-arithmetic | 4 | 1/4 | 1/4 | yes |
| money-arithmetic | 5 | 4/4 | 2/4 | yes |
| money-arithmetic | 6 | 4/4 | 3/4 | yes |
| money-arithmetic | 7 | 4/4 | 1/4 | yes |
| money-tests | 1 | 5/5 | 3/5 | yes |
| money-tests | 2 | 4/4 | 1/4 | yes |
| money-tests | 3 | 4/4 | 0/4 | yes |
| money-tests | 4 | 4/4 | 3/4 | yes |
| money-tests | 5 | 4/4 | 3/4 | yes |
| money-tests | 6 | 4/4 | 1/4 | yes |
| money-tests | 7 | 5/5 | 3/5 | yes |
| pii-and-card-data | 1 | 3/4 | 0/4 | yes |
| pii-and-card-data | 2 | 4/4 | 4/4 | yes |
| pii-and-card-data | 3 | 3/3 | 2/3 | yes |
| pii-and-card-data | 4 | 4/4 | 4/4 | yes |
| pii-and-card-data | 5 | 4/4 | 1/4 | yes |
| pii-and-card-data | 6 | 2/4 | 0/4 | yes |
| pii-and-card-data | 7 | 2/4 | 1/4 | yes |
| reconciliation | 1 | 5/5 | 3/5 | yes |
| reconciliation | 2 | 1/4 | 0/4 | yes |
| reconciliation | 3 | 4/4 | 0/4 | yes |
| reconciliation | 4 | 3/4 | 2/4 | yes |
| reconciliation | 5 | 4/4 | 2/4 | yes |
| reconciliation | 6 | 4/4 | 0/4 | yes |
| reconciliation | 7 | 4/4 | 0/4 | yes |
| transaction-classification | 1 | 4/5 | 1/5 | yes |
| transaction-classification | 2 | 4/4 | 0/4 | yes |
| transaction-classification | 3 | 3/3 | 2/3 | yes |
| transaction-classification | 4 | 4/4 | 1/4 | yes |
| transaction-classification | 5 | 3/3 | 2/3 | yes |
| transaction-classification | 6 | 4/4 | 0/4 | yes |
| transaction-classification | 7 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 1/5 | yes |
| webhook-handling | 2 | 4/4 | 0/4 | yes |
| webhook-handling | 3 | 4/4 | 3/4 | yes |
| webhook-handling | 4 | 4/4 | 3/4 | yes |
| webhook-handling | 5 | 0/4 | 0/4 | yes |
| webhook-handling | 6 | 4/4 | 0/4 | yes |
| webhook-handling | 7 | 4/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields above.
- `skills/<skill>.json`: one record per (eval, condition): the exact `claude` invocation, the subject's final answer, tokens, stop reason, wall time, the files it wrote with sha256, and the grader's verdict and evidence per expectation.
- No noise-rule re-run was needed.
- `raw-20261109T103432Z-fa81209.tar.gz`, attached to the GitHub release: `raw/<skill>/<eval>-<condition>-1/` with the subject and grader transcripts and the files the subject wrote.
