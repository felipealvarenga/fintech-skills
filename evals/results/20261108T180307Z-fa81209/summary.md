# Evaluation results, run 20261108T180307Z-fa81209

Date 2026-11-08, 18:03 to 19:45 UTC. Subject model `claude-sonnet-5-5`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless. Development prompts (`skills/*/evals/evals.json`).

**With the skill installed, 80.8% of expectations passed (299 of 370). Without it, 23.5% (87 of 370). Lift: 57.3 points.** 13 skills, 7 prompts each, one run per prompt per condition: 182 subject sessions, 182 grader sessions, 0 grader errors, 0 max-turn stops.

## Changes since the previous run

The previous run, [20261108T143507Z-ae8adc1](../20261108T143507Z-ae8adc1/summary.md), measured 78.1% with and 25.7% without (289 and 95 of 370) on the skills at `eadbaa9`, with `claude-sonnet-5-5` as subject and grader. Its with-condition failures concentrated in brazil-payment-rails (55.2%, three evals lower with the skill than without by one expectation each, one adversarial prompt that never opened the skill) and pii-and-card-data.

The skills measured here are the release candidate `fa81209`. brazil-payment-rails: the description names the static-QR and payer-name requests it had not opened for; a table of common pushbacks with the compliant build; a MED return is a state and a record (ledger reversal, order to disputed, dispute record, fulfilment hold, the 80-day window said in the answer); a boleto change stores the linha digitável and nosso número, handles late and expired payment and states D+1 in the code; a card-installment change posts MDR as a fee line, models anticipation and keeps chargeback and estorno distinct. pii-and-card-data: a refusal to store a PAN or CVV names PCI DSS scope as the reason; a pushback table. All thirteen skills: leaving the code unchanged and listing the risks is never the compliant version. Earlier commits between the runs (`4fcaf65`, `ae172ad`) also changed webhook-handling (store-then-acknowledge crash window, refunds and disputes as records, Stripe's retry and dual-event behaviour), idempotent-payments (processor key retention bounds same-key retries), money-tests (429 against 400, fake processor entries, scrubbed re-recording) and the MED and NFS-e facts in brazil-payment-rails, after two independent pre-launch reviews.

Two things about the measurement itself changed, both before this run started and both stated here:

- The grader is blinded to the condition: the runner removes the installed-skill list, the `Skill` tool calls and every read under `.claude/skills/` from the transcript it grades (`4fcaf65`). The previous runs' graders saw those reads. The without condition, which the blinding cannot help, moved from 25.7% to 23.5%.
- `brazil-payment-rails` eval 5, expectation 3: "States the MED window correctly (claim within 80 days since 1 September 2026) and that MED covers fraud or operational failure, not remorse" lost the date, which was wrong (MED 2.0 is Resolução BCB 493/2025; the 80-day claim window predates it). The other 90 prompts and their expectations are identical to the previous run.

## Method

- Runner: `scripts/run_evals.py` at `fa81209` on `main` (the install excludes everything under `evals/`; the grader transcript is blinded as above). One invocation per skill, in this order: double-entry-ledger, brazil-payment-rails, fintech-audit, money-arithmetic, idempotent-payments, webhook-handling, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, money-tests, 18:03 to 19:45 UTC. This folder combines the 13 run directories; `run_id` inside each `skills/<skill>.json` is that skill's own invocation.
- Skills measured: `fa81209`, the release candidate; `skills_dirty: false`, a clean checkout.
- Install: `SKILL.md`, `references/` and `scripts/` copied to `.claude/skills/<name>/` in a fresh temporary project; `installed_paths` in each `skills/<skill>.json` lists exactly what the subject could read. fintech-audit installs all 13 skills in the with condition.
- Subject session: `claude -p --output-format json --model claude-sonnet-5-5 --max-turns 30 --tools Read,Write,Edit,Glob,Grep,Skill --setting-sources project --strict-mcp-config --permission-mode acceptEdits --permission-prompts none --no-session-persistence`, with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`. No Bash, no web tools, no MCP servers.
- Grader session: `claude-sonnet-5-5`, no tools. It receives the prompt, the expectations, the subject's final answer, the blinded transcript and every file the subject wrote, and returns one verdict with evidence per expectation.
- Pass rate = passed expectations / (passed + failed). Each eval has 3 to 6 expectations; each skill has 27 to 30 per condition. The two conditions see the same prompts, fixtures and expectations.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 80.8% | 299 | 71 | 4,637,930 | 4,331,438 | 4174 |
| without | 23.5% | 87 | 283 | 2,227,587 | 1,755,272 | 1981 |

## Per skill

| Skill | With | Without | Lift (points) | Previous run with / without | Expectations per condition |
|---|---|---|---|---|---|
| webhook-handling | 86.2% | 6.9% | 79.3 | 86.2% / 6.9% | 29 |
| transaction-classification | 100.0% | 22.2% | 77.8 | 100.0% / 18.5% | 27 |
| brazil-payment-rails | 89.7% | 20.7% | 69.0 | 55.2% / 17.2% | 29 |
| money-tests | 96.7% | 30.0% | 66.7 | 93.3% / 43.3% | 30 |
| idempotent-payments | 85.7% | 21.4% | 64.3 | 85.7% / 21.4% | 28 |
| reconciliation | 72.4% | 10.3% | 62.1 | 75.9% / 17.2% | 29 |
| double-entry-ledger | 82.1% | 25.0% | 57.1 | 78.6% / 39.3% | 28 |
| interest-and-amortization | 71.4% | 17.9% | 53.6 | 67.9% / 21.4% | 28 |
| money-arithmetic | 83.3% | 33.3% | 50.0 | 83.3% / 36.7% | 30 |
| audit-trail | 74.1% | 25.9% | 48.1 | 70.4% / 22.2% | 27 |
| accounting-sync | 67.9% | 21.4% | 46.4 | 78.6% / 14.3% | 28 |
| fintech-audit | 76.7% | 33.3% | 43.3 | 76.7% / 36.7% | 30 |
| pii-and-card-data | 63.0% | 37.0% | 25.9 | 63.0% / 37.0% | 27 |

## The skills changed since the previous run

| Skill | Previous with / without | This run with / without | With-condition failures, previous to this run |
|---|---|---|---|
| brazil-payment-rails | 55.2% / 17.2% | 89.7% / 20.7% | 13 to 3 |
| pii-and-card-data | 63.0% / 37.0% | 63.0% / 37.0% | 10 to 10 |

webhook-handling eval 5 ("we trust Stripe, no API call"): with 0/4 in the previous run, 0/4 here; without 0/4 and 0/4. brazil-payment-rails eval 4 ("keep the static QR, we match by payer name"): with 0/4 then, 2/4 here.

## Launch bar and the noise rule

Stated before this run: brazil-payment-rails at or above 70% with the skill; no eval lower with the skill than without; every skill with at least 10 points of lift. One run per prompt per condition, so an eval counts as lower only when it drops by two or more expectations; a drop of one triggers one re-run of that skill, and both results are reported.

- brazil-payment-rails with the skill: 89.7%.
- Lowest lift: pii-and-card-data at 25.9 points.
- Evals lower with the skill by two or more expectations: none.
- Evals lower by one expectation: pii-and-card-data eval 7.
- Re-run of pii-and-card-data (`reruns/pii-and-card-data.json`, same commit, same prompts, 20261108T194638Z-fa81209): with 18/27, without 10/27; per eval (with / without): 1: 3/0, 2: 4/4, 3: 3/1, 4: 4/3, 5: 2/1, 6: 0/0, 7: 2/1. The pack numbers above are from the first run only; the re-run is reported, not substituted.

## Reading the numbers

- The without condition is the noise gauge: nothing it sees changed except one expectation, and it moved from 25.7% to 23.5% at pack level, up to 14 points for one skill (double-entry-ledger). Single-skill moves of that size are within run-to-run variation. The pack-level gap of 57.3 points over 370 expectations per condition is many times that variation; with one run per prompt and expectations that are correlated within a response, no confidence interval is claimed.
- In 2 of 91 with-condition sessions the agent never opened the skill (accounting-sync eval 4, webhook-handling eval 5); the previous run had 1 (brazil-payment-rails eval 4).
- The with condition used 2.1x the subject tokens of the without condition.
- The remaining with-condition failures are largest in pii-and-card-data (10) and accounting-sync (9).
- These are development prompts: the skills were revised against earlier runs' failures on them. The held-out set in `evals/heldout/` (two prompts per skill, never read when editing a skill) is measured in its own folder on the same commit.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 5/5 | 1/5 | yes |
| accounting-sync | 2 | 4/4 | 3/4 | yes |
| accounting-sync | 3 | 2/3 | 0/3 | yes |
| accounting-sync | 4 | 0/4 | 0/4 | no |
| accounting-sync | 5 | 4/4 | 0/4 | yes |
| accounting-sync | 6 | 2/4 | 1/4 | yes |
| accounting-sync | 7 | 2/4 | 1/4 | yes |
| audit-trail | 1 | 4/4 | 1/4 | yes |
| audit-trail | 2 | 3/4 | 1/4 | yes |
| audit-trail | 3 | 3/4 | 2/4 | yes |
| audit-trail | 4 | 3/4 | 1/4 | yes |
| audit-trail | 5 | 2/4 | 0/4 | yes |
| audit-trail | 6 | 2/3 | 0/3 | yes |
| audit-trail | 7 | 3/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 5/5 | 1/5 | yes |
| brazil-payment-rails | 2 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 3 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 4 | 2/4 | 0/4 | yes |
| brazil-payment-rails | 5 | 3/4 | 2/4 | yes |
| brazil-payment-rails | 6 | 4/4 | 1/4 | yes |
| brazil-payment-rails | 7 | 4/4 | 0/4 | yes |
| double-entry-ledger | 1 | 4/4 | 0/4 | yes |
| double-entry-ledger | 2 | 3/4 | 1/4 | yes |
| double-entry-ledger | 3 | 4/4 | 1/4 | yes |
| double-entry-ledger | 4 | 4/4 | 2/4 | yes |
| double-entry-ledger | 5 | 2/4 | 0/4 | yes |
| double-entry-ledger | 6 | 3/4 | 3/4 | yes |
| double-entry-ledger | 7 | 3/4 | 0/4 | yes |
| fintech-audit | 1 | 6/6 | 3/6 | yes |
| fintech-audit | 2 | 4/4 | 1/4 | yes |
| fintech-audit | 3 | 3/4 | 2/4 | yes |
| fintech-audit | 4 | 3/4 | 2/4 | yes |
| fintech-audit | 5 | 1/4 | 1/4 | yes |
| fintech-audit | 6 | 3/4 | 1/4 | yes |
| fintech-audit | 7 | 3/4 | 0/4 | yes |
| idempotent-payments | 1 | 5/5 | 2/5 | yes |
| idempotent-payments | 2 | 4/4 | 1/4 | yes |
| idempotent-payments | 3 | 4/4 | 1/4 | yes |
| idempotent-payments | 4 | 2/4 | 1/4 | yes |
| idempotent-payments | 5 | 4/4 | 0/4 | yes |
| idempotent-payments | 6 | 3/3 | 1/3 | yes |
| idempotent-payments | 7 | 2/4 | 0/4 | yes |
| interest-and-amortization | 1 | 5/5 | 3/5 | yes |
| interest-and-amortization | 2 | 2/3 | 1/3 | yes |
| interest-and-amortization | 3 | 2/4 | 1/4 | yes |
| interest-and-amortization | 4 | 1/4 | 0/4 | yes |
| interest-and-amortization | 5 | 4/4 | 0/4 | yes |
| interest-and-amortization | 6 | 2/4 | 0/4 | yes |
| interest-and-amortization | 7 | 4/4 | 0/4 | yes |
| money-arithmetic | 1 | 5/5 | 4/5 | yes |
| money-arithmetic | 2 | 4/4 | 1/4 | yes |
| money-arithmetic | 3 | 4/5 | 0/5 | yes |
| money-arithmetic | 4 | 2/4 | 1/4 | yes |
| money-arithmetic | 5 | 3/4 | 1/4 | yes |
| money-arithmetic | 6 | 4/4 | 2/4 | yes |
| money-arithmetic | 7 | 3/4 | 1/4 | yes |
| money-tests | 1 | 5/5 | 3/5 | yes |
| money-tests | 2 | 3/4 | 1/4 | yes |
| money-tests | 3 | 4/4 | 0/4 | yes |
| money-tests | 4 | 4/4 | 2/4 | yes |
| money-tests | 5 | 4/4 | 2/4 | yes |
| money-tests | 6 | 4/4 | 1/4 | yes |
| money-tests | 7 | 5/5 | 0/5 | yes |
| pii-and-card-data | 1 | 3/4 | 1/4 | yes |
| pii-and-card-data | 2 | 4/4 | 4/4 | yes |
| pii-and-card-data | 3 | 3/3 | 1/3 | yes |
| pii-and-card-data | 4 | 4/4 | 3/4 | yes |
| pii-and-card-data | 5 | 2/4 | 0/4 | yes |
| pii-and-card-data | 6 | 1/4 | 0/4 | yes |
| pii-and-card-data | 7 | 0/4 | 1/4 | yes |
| reconciliation | 1 | 5/5 | 1/5 | yes |
| reconciliation | 2 | 1/4 | 0/4 | yes |
| reconciliation | 3 | 2/4 | 0/4 | yes |
| reconciliation | 4 | 1/4 | 0/4 | yes |
| reconciliation | 5 | 4/4 | 2/4 | yes |
| reconciliation | 6 | 4/4 | 0/4 | yes |
| reconciliation | 7 | 4/4 | 0/4 | yes |
| transaction-classification | 1 | 5/5 | 1/5 | yes |
| transaction-classification | 2 | 4/4 | 0/4 | yes |
| transaction-classification | 3 | 3/3 | 2/3 | yes |
| transaction-classification | 4 | 4/4 | 0/4 | yes |
| transaction-classification | 5 | 3/3 | 2/3 | yes |
| transaction-classification | 6 | 4/4 | 0/4 | yes |
| transaction-classification | 7 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 1/5 | yes |
| webhook-handling | 2 | 4/4 | 0/4 | yes |
| webhook-handling | 3 | 4/4 | 0/4 | yes |
| webhook-handling | 4 | 4/4 | 0/4 | yes |
| webhook-handling | 5 | 0/4 | 0/4 | no |
| webhook-handling | 6 | 4/4 | 0/4 | yes |
| webhook-handling | 7 | 4/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields above.
- `skills/<skill>.json`: one record per (eval, condition): the exact `claude` invocation, the subject's final answer, tokens, stop reason, wall time, the files it wrote with sha256, and the grader's verdict and evidence per expectation.
- `reruns/<skill>.json`: the noise-rule re-run of one skill, same shape.
- `raw-20261108T180307Z-fa81209.tar.gz`, attached to the GitHub release: `raw/<skill>/<eval>-<condition>-1/` (and `raw/reruns/...`) with the subject and grader transcripts and the files the subject wrote.
