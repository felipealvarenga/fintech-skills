# Evaluation results, run 20261125T151436Z-fa81209

Date 2026-11-25. Subject model `gemini-4-neon-high` via Antigravity CLI (`agy` 1.5.17, headless). Grader model `claude-sonnet-5-5` (2.1.332 (Claude Code), headless, effort `xhigh`). Development prompts (`skills/*/evals/evals.json`). Same skills text, prompts, expectations and blinded grader as the `claude-sonnet-5-5` ([20261108T180307Z-fa81209](../20261108T180307Z-fa81209/summary.md)) and `claude-opus-5-5` ([20261109T103432Z-fa81209](../20261109T103432Z-fa81209/summary.md)) runs on `fa81209`. Thinking tokens were 48.9% of the subject's output tokens with the skill and 65.9% without.

**With the skill installed, 92.4% of expectations passed (342 of 370). Without it, 42.8% (155 of 362). Lift: 49.6 points.** 13 skills, 7 prompts each, one run per prompt per condition: 182 subject sessions, 180 grader sessions, 0 with-condition error expectations, 8 without-condition error expectations (2 `without` sessions hit headless permission aborts: `accounting-sync` eval 6 tried writing outside the workspace and `fintech-audit` eval 7 invoked `fintech-audit` as a shell command).

## Method and first-attempt note

- **Skills measured:** Checkout `24568b6`, whose 13 `SKILL.md` files, `references/` and `evals/` are byte-for-byte identical to `fa81209` (the only diff under `skills/` since `fa81209` is the unexecuted `skills/fintech-audit/scripts/money_lint.py` hardening from `3b36f10`).
- **Isolation:** Each `agy` subject ran in a fresh temporary git repository with an isolated temporary `HOME` (symlinking only CLI auth/config so host `~/.agents/skills/` and `~/.gemini/config/skills/` were invisible). The `with` condition copied the target skill (or all 13 for `fintech-audit`) into `.agents/skills/<name>/` excluding `evals/`; `without` installed nothing. `allowNonWorkspaceAccess` was set to `false`, read-only inspection commands (`ls`, `find`, `rg`, `grep`, `sort`, etc.) were allowed to match Claude Code's `Glob`/`Grep`, and code-execution/shell/network binaries (`python3`, `pytest`, `node`, `bash`, `curl`, etc.) were denied.
- **Blinding:** `scripts/run_evals.py` stripped all `.agents/skills/` tool calls and scrubbed `.agents`/`.claude` lines from workspace listings before sending the transcript to the `claude-sonnet-5-5` grader (0 harness leaks).
- **First-attempt headless abort note:** An initial full pass (`20261125T151436Z`, before `sort`/`which`/`echo`/`true` were classified in `AGY_SETTINGS`) scored **86.5% with (320/370)** vs **39.7% without (147/370)** (+46.8 points, 91/91 opened) with 21 of 182 sessions (`10` with, `11` without, across `20` prompts) aborted immediately with empty responses by `agy` headless permission checks. After fixing `AGY_SETTINGS`, both conditions for those exact 20 affected prompts were re-run (`20261125T210615Z`, scoring 94.0% with vs 40.0% without) and substituted here; the other 71 clean prompts are untouched from the first pass.

## Pack level

| Condition | Pass rate | Passed | Failed | Errors | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|---|
| with | 92.4% | 342 | 28 | 0 | 32,948,053 | 4,210,365 | 36763 |
| without | 42.8% | 155 | 207 | 8 | 10,816,283 | 1,530,409 | 15351 |

## Per skill

| Skill | With | Without | Lift (points) | Opus 5.5 with / without | Sonnet 5.5 with / without | Expectations (with/without) |
|---|---|---|---|---|---|---|
| reconciliation | 93.1% | 24.1% | 69.0 | 86.2% / 24.1% | 72.4% / 10.3% | 29/29 |
| fintech-audit | 86.7% | 23.1% | 63.6 | 83.3% / 40.0% | 76.7% / 33.3% | 30/26 |
| brazil-payment-rails | 100.0% | 37.9% | 62.1 | 86.2% / 31.0% | 89.7% / 20.7% | 29/29 |
| idempotent-payments | 100.0% | 39.3% | 60.7 | 100.0% / 35.7% | 85.7% / 21.4% | 28/28 |
| accounting-sync | 85.7% | 29.2% | 56.5 | 85.7% / 28.6% | 67.9% / 21.4% | 28/24 |
| transaction-classification | 92.6% | 37.0% | 55.6 | 96.3% / 25.9% | 100.0% / 22.2% | 27/27 |
| webhook-handling | 96.6% | 41.4% | 55.2 | 86.2% / 27.6% | 86.2% / 6.9% | 29/29 |
| interest-and-amortization | 89.3% | 35.7% | 53.6 | 78.6% / 32.1% | 71.4% / 17.9% | 28/28 |
| money-tests | 96.7% | 50.0% | 46.7 | 100.0% / 46.7% | 96.7% / 30.0% | 30/30 |
| double-entry-ledger | 96.4% | 50.0% | 46.4 | 92.9% / 39.3% | 82.1% / 25.0% | 28/28 |
| audit-trail | 88.9% | 48.1% | 40.7 | 85.2% / 33.3% | 74.1% / 25.9% | 27/27 |
| money-arithmetic | 90.0% | 70.0% | 20.0 | 90.0% / 46.7% | 83.3% / 33.3% | 30/30 |
| pii-and-card-data | 85.2% | 66.7% | 18.5 | 81.5% / 44.4% | 63.0% / 37.0% | 27/27 |

## Reading the numbers

- In 0 of 91 with-condition sessions the agent never opened the skill (none).
- Lowest per-skill lift: `pii-and-card-data` at 18.5 points (baseline 66.7%).
- Evals lower with the skill by two or more expectations: money-arithmetic eval 4; by one: none.
- These are development prompts (in-sample). The out-of-sample held-out set for `gemini-4-neon-high` is in [20261125T210621Z-fa81209-heldout](../20261125T210621Z-fa81209-heldout/summary.md).

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 5/5 | 2/5 | yes |
| accounting-sync | 2 | 4/4 | 0/4 | yes |
| accounting-sync | 3 | 2/3 | 2/3 | yes |
| accounting-sync | 4 | 2/4 | 2/4 | yes |
| accounting-sync | 5 | 4/4 | 0/4 | yes |
| accounting-sync | 6 | 3/4 | 0/0 (4 err) | yes |
| accounting-sync | 7 | 4/4 | 1/4 | yes |
| audit-trail | 1 | 4/4 | 4/4 | yes |
| audit-trail | 2 | 4/4 | 1/4 | yes |
| audit-trail | 3 | 4/4 | 1/4 | yes |
| audit-trail | 4 | 3/4 | 2/4 | yes |
| audit-trail | 5 | 3/4 | 1/4 | yes |
| audit-trail | 6 | 3/3 | 1/3 | yes |
| audit-trail | 7 | 3/4 | 3/4 | yes |
| brazil-payment-rails | 1 | 5/5 | 3/5 | yes |
| brazil-payment-rails | 2 | 4/4 | 1/4 | yes |
| brazil-payment-rails | 3 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 4 | 4/4 | 1/4 | yes |
| brazil-payment-rails | 5 | 4/4 | 3/4 | yes |
| brazil-payment-rails | 6 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 7 | 4/4 | 1/4 | yes |
| double-entry-ledger | 1 | 4/4 | 3/4 | yes |
| double-entry-ledger | 2 | 4/4 | 3/4 | yes |
| double-entry-ledger | 3 | 4/4 | 4/4 | yes |
| double-entry-ledger | 4 | 4/4 | 0/4 | yes |
| double-entry-ledger | 5 | 3/4 | 2/4 | yes |
| double-entry-ledger | 6 | 4/4 | 0/4 | yes |
| double-entry-ledger | 7 | 4/4 | 2/4 | yes |
| fintech-audit | 1 | 5/6 | 3/6 | yes |
| fintech-audit | 2 | 4/4 | 0/4 | yes |
| fintech-audit | 3 | 3/4 | 0/4 | yes |
| fintech-audit | 4 | 3/4 | 2/4 | yes |
| fintech-audit | 5 | 3/4 | 0/4 | yes |
| fintech-audit | 6 | 4/4 | 1/4 | yes |
| fintech-audit | 7 | 4/4 | 0/0 (4 err) | yes |
| idempotent-payments | 1 | 5/5 | 5/5 | yes |
| idempotent-payments | 2 | 4/4 | 0/4 | yes |
| idempotent-payments | 3 | 4/4 | 0/4 | yes |
| idempotent-payments | 4 | 4/4 | 2/4 | yes |
| idempotent-payments | 5 | 4/4 | 3/4 | yes |
| idempotent-payments | 6 | 3/3 | 1/3 | yes |
| idempotent-payments | 7 | 4/4 | 0/4 | yes |
| interest-and-amortization | 1 | 5/5 | 5/5 | yes |
| interest-and-amortization | 2 | 2/3 | 1/3 | yes |
| interest-and-amortization | 3 | 3/4 | 1/4 | yes |
| interest-and-amortization | 4 | 3/4 | 3/4 | yes |
| interest-and-amortization | 5 | 4/4 | 0/4 | yes |
| interest-and-amortization | 6 | 4/4 | 0/4 | yes |
| interest-and-amortization | 7 | 4/4 | 0/4 | yes |
| money-arithmetic | 1 | 5/5 | 4/5 | yes |
| money-arithmetic | 2 | 4/4 | 3/4 | yes |
| money-arithmetic | 3 | 5/5 | 2/5 | yes |
| money-arithmetic | 4 | 1/4 | 3/4 | yes |
| money-arithmetic | 5 | 4/4 | 2/4 | yes |
| money-arithmetic | 6 | 4/4 | 4/4 | yes |
| money-arithmetic | 7 | 4/4 | 3/4 | yes |
| money-tests | 1 | 4/5 | 3/5 | yes |
| money-tests | 2 | 4/4 | 1/4 | yes |
| money-tests | 3 | 4/4 | 0/4 | yes |
| money-tests | 4 | 4/4 | 3/4 | yes |
| money-tests | 5 | 4/4 | 3/4 | yes |
| money-tests | 6 | 4/4 | 1/4 | yes |
| money-tests | 7 | 5/5 | 4/5 | yes |
| pii-and-card-data | 1 | 3/4 | 2/4 | yes |
| pii-and-card-data | 2 | 4/4 | 4/4 | yes |
| pii-and-card-data | 3 | 3/3 | 2/3 | yes |
| pii-and-card-data | 4 | 4/4 | 4/4 | yes |
| pii-and-card-data | 5 | 4/4 | 1/4 | yes |
| pii-and-card-data | 6 | 3/4 | 3/4 | yes |
| pii-and-card-data | 7 | 2/4 | 2/4 | yes |
| reconciliation | 1 | 5/5 | 2/5 | yes |
| reconciliation | 2 | 4/4 | 0/4 | yes |
| reconciliation | 3 | 4/4 | 1/4 | yes |
| reconciliation | 4 | 2/4 | 2/4 | yes |
| reconciliation | 5 | 4/4 | 2/4 | yes |
| reconciliation | 6 | 4/4 | 0/4 | yes |
| reconciliation | 7 | 4/4 | 0/4 | yes |
| transaction-classification | 1 | 5/5 | 1/5 | yes |
| transaction-classification | 2 | 3/4 | 1/4 | yes |
| transaction-classification | 3 | 3/3 | 2/3 | yes |
| transaction-classification | 4 | 3/4 | 1/4 | yes |
| transaction-classification | 5 | 3/3 | 3/3 | yes |
| transaction-classification | 6 | 4/4 | 1/4 | yes |
| transaction-classification | 7 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 2/5 | yes |
| webhook-handling | 2 | 4/4 | 0/4 | yes |
| webhook-handling | 3 | 4/4 | 4/4 | yes |
| webhook-handling | 4 | 4/4 | 3/4 | yes |
| webhook-handling | 5 | 4/4 | 0/4 | yes |
| webhook-handling | 6 | 3/4 | 0/4 | yes |
| webhook-handling | 7 | 4/4 | 3/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields.
- `skills/<skill>.json`: one record per (eval, condition) with the `agy` subject invocation, final answer, tokens, files written with sha256, and the `claude-sonnet-5-5` grader's verdict and evidence per expectation.
- `raw-20261125T151436Z-fa81209.tar.gz`: subject and grader transcripts and produced files.
