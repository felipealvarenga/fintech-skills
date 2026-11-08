# Evaluation results, run 20261108T053526Z-ee4f998

Date 2026-11-08, 05:35 to 07:05 UTC. Subject model `claude-sonnet-5-5`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless.

**With the skill installed, 72.2% of expectations passed (267 of 370). Without it, 26.8% (99 of 370). Lift: 45.4 points.** 13 skills, 7 prompts each, one run per prompt per condition: 182 subject sessions, 182 grader sessions, 0 grader errors.

## Changes since the previous run

The previous run, [20261108T035910Z-c7e767e](../20261108T035910Z-c7e767e/summary.md), measured 62.2% with and 25.4% without (230 and 94 of 370) on the skills at `c7e767e`. Reading its 140 with-condition failures showed that in 48 of them the agent listed the tests as a next step instead of writing them, and that 6 of the 91 with-condition sessions never opened the skill, all on adversarial prompts.

Commit `ee4f998` answered both: every `SKILL.md` now asks for the test file in the same change even when the agent cannot run it, and five descriptions name the adversarial requests (keep floats, patch a cent drift with round(), a display-only schedule, force the last balance to zero, delete or skip a failing money test, seed staging from production, show a full document or card number, an auditor asking who changed what). Two fixtures were rewritten because both conditions did nothing with them: `money-arithmetic` eval 4 (`billing_float.py` now has an unrounded float loop sum) and `audit-trail` eval 5 (`admin_tool.py` now masks the CPF). Those two evals are therefore not comparable across the runs; the other 89 prompts, fixtures and expectations are identical.

No eval prompt or expectation was changed after seeing a grader verdict.

## Method

- Runner: `scripts/run_evals.py` at `c7e767e` (pull request #1) plus one parser fix that accepts a grader verdict wrapped in a ```json fence; the fix is committed after #1 merges. One invocation per skill, in this order: double-entry-ledger, brazil-payment-rails, fintech-audit, money-arithmetic, idempotent-payments, webhook-handling, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, money-tests, 05:35 to 07:05 UTC. This folder combines the 13 run directories; `run_id` inside each `skills/<skill>.json` is that skill's own invocation.
- Skills measured: `ee4f998`, the head of `main` at the time of the run.
- Install: `SKILL.md`, `references/` and `scripts/` copied to `.claude/skills/<name>/` in a fresh temporary project. Nothing under `evals/` is installed, so the subject cannot read the reference implementations or the expectations. The runner's worktree had `skills/*/evals/vectors` deleted as a second guard and carried the patched runner script; `skills_dirty: true` in the per-skill files records those two things and nothing else.
- fintech-audit installs all 13 skills in the with condition, because it delegates to the other twelve.
- Subject session: `claude -p --output-format json --model claude-sonnet-5-5 --max-turns 30 --tools Read,Write,Edit,Glob,Grep,Skill --setting-sources project --strict-mcp-config --permission-mode acceptEdits --permission-prompts none --no-session-persistence`, with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`. No Bash, no web tools, no MCP servers. Three built-in skills (design, doctor, plugin-authoring) still load in both conditions; none concerns money. The prompt is the eval prompt verbatim; fixture files listed in `evals.json` are copied to `src/` first.
- Grader session: same model, no tools. It receives the prompt, the expectations, the subject's final answer, the full subject transcript and every file the subject wrote, and returns one verdict with evidence per expectation. The verdicts and evidence are in `skills/<skill>.json`.
- Pass rate = passed expectations / (passed + failed). Each eval has 3 to 6 expectations; each skill has 27 to 30 per condition. The two conditions see the same prompts, fixtures and expectations.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 72.2% | 267 | 103 | 3,999,438 | 3,749,112 | 3487 |
| without | 26.8% | 99 | 271 | 2,251,970 | 1,802,061 | 1903 |

Tokens are the sums the Claude Code JSON result reports (input, output and cache tokens). Wall seconds add subject and grader sessions.

## Per skill

| Skill | With | Without | Lift (points) | Previous run with / without | Expectations per condition |
|---|---|---|---|---|---|
| idempotent-payments | 92.9% | 25.0% | 67.9 | 60.7% / 21.4% | 28 |
| webhook-handling | 69.0% | 6.9% | 62.1 | 58.6% / 13.8% | 29 |
| audit-trail | 77.8% | 22.2% | 55.6 | 48.1% / 25.9% | 27 |
| brazil-payment-rails | 69.0% | 17.2% | 51.7 | 51.7% / 17.2% | 29 |
| accounting-sync | 64.3% | 14.3% | 50.0 | 53.6% / 14.3% | 28 |
| double-entry-ledger | 82.1% | 32.1% | 50.0 | 75.0% / 39.3% | 28 |
| interest-and-amortization | 67.9% | 17.9% | 50.0 | 53.6% / 21.4% | 28 |
| money-arithmetic | 83.3% | 33.3% | 50.0 | 73.3% / 36.7% | 30 |
| reconciliation | 72.4% | 24.1% | 48.3 | 69.0% / 17.2% | 29 |
| transaction-classification | 55.6% | 22.2% | 33.3 | 55.6% / 14.8% | 27 |
| fintech-audit | 76.7% | 50.0% | 26.7 | 76.7% / 33.3% | 30 |
| pii-and-card-data | 66.7% | 40.7% | 25.9 | 63.0% / 37.0% | 27 |
| money-tests | 60.0% | 40.0% | 20.0 | 66.7% / 36.7% | 30 |

## Reading the numbers

- One run per prompt per condition. The without condition is the noise gauge: nothing it sees changed between the runs, and it moved from 25.4% to 26.8% at pack level, but up to 17 points for one skill (fintech-audit). Per-skill differences under about 15 points are noise; the pack-level gap of 45.4 points over 370 expectations per condition is not, and neither is the 10.0-point move of the with condition between the runs.
- In 1 of 91 with-condition sessions the agent never opened the skill (accounting-sync eval 4), down from 6 in the previous run. That session counts against the with condition as run.
- The evals where with scored below without are brazil-payment-rails eval 5, reconciliation eval 2, each by one expectation with the skill opened. The previous run had 3 such evals (idempotent-payments eval 4, interest-and-amortization eval 4, money-arithmetic eval 4), all adversarial prompts where the skill was not opened; none of them regressed this time.
- Cut rule stated before the first run: a skill with under 10 points of lift on its own seven evals is folded into another or removed. The lowest lift is money-tests at 20.0 points, so nothing was cut.
- The with condition used 1.8x the subject tokens of the without condition: it reads the skill and it writes the tests the skill asks for.
- The remaining with-condition failures cluster in transaction-classification and money-tests (12 each): calibration and monitoring work the prompt did not name, and test infrastructure (injected clock, fake processor, mutation kill rate) that the agent describes rather than writes. Those are the next targets; they will be measured by a new run, not by editing this one.
- The grader is a model reading transcripts against written expectations. Expectations were written before the run and are in each skill's `evals/evals.json`; a reader can re-grade any session from `raw/`.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 5/5 | 1/5 | yes |
| accounting-sync | 2 | 4/4 | 2/4 | yes |
| accounting-sync | 3 | 2/3 | 0/3 | yes |
| accounting-sync | 4 | 0/4 | 0/4 | no |
| accounting-sync | 5 | 3/4 | 0/4 | yes |
| accounting-sync | 6 | 2/4 | 1/4 | yes |
| accounting-sync | 7 | 2/4 | 0/4 | yes |
| audit-trail | 1 | 4/4 | 1/4 | yes |
| audit-trail | 2 | 3/4 | 0/4 | yes |
| audit-trail | 3 | 3/4 | 2/4 | yes |
| audit-trail | 4 | 3/4 | 1/4 | yes |
| audit-trail | 5 | 2/4 | 0/4 | yes |
| audit-trail | 6 | 3/3 | 0/3 | yes |
| audit-trail | 7 | 3/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 5/5 | 0/5 | yes |
| brazil-payment-rails | 2 | 3/4 | 0/4 | yes |
| brazil-payment-rails | 3 | 4/4 | 2/4 | yes |
| brazil-payment-rails | 4 | 2/4 | 0/4 | yes |
| brazil-payment-rails | 5 | 1/4 | 2/4 | yes |
| brazil-payment-rails | 6 | 4/4 | 1/4 | yes |
| brazil-payment-rails | 7 | 1/4 | 0/4 | yes |
| double-entry-ledger | 1 | 4/4 | 0/4 | yes |
| double-entry-ledger | 2 | 3/4 | 3/4 | yes |
| double-entry-ledger | 3 | 4/4 | 1/4 | yes |
| double-entry-ledger | 4 | 4/4 | 1/4 | yes |
| double-entry-ledger | 5 | 2/4 | 1/4 | yes |
| double-entry-ledger | 6 | 3/4 | 3/4 | yes |
| double-entry-ledger | 7 | 3/4 | 0/4 | yes |
| fintech-audit | 1 | 5/6 | 3/6 | yes |
| fintech-audit | 2 | 4/4 | 2/4 | yes |
| fintech-audit | 3 | 3/4 | 2/4 | yes |
| fintech-audit | 4 | 3/4 | 2/4 | yes |
| fintech-audit | 5 | 1/4 | 1/4 | yes |
| fintech-audit | 6 | 3/4 | 2/4 | yes |
| fintech-audit | 7 | 4/4 | 3/4 | yes |
| idempotent-payments | 1 | 5/5 | 1/5 | yes |
| idempotent-payments | 2 | 3/4 | 1/4 | yes |
| idempotent-payments | 3 | 4/4 | 2/4 | yes |
| idempotent-payments | 4 | 3/4 | 2/4 | yes |
| idempotent-payments | 5 | 4/4 | 0/4 | yes |
| idempotent-payments | 6 | 3/3 | 1/3 | yes |
| idempotent-payments | 7 | 4/4 | 0/4 | yes |
| interest-and-amortization | 1 | 5/5 | 3/5 | yes |
| interest-and-amortization | 2 | 1/3 | 1/3 | yes |
| interest-and-amortization | 3 | 2/4 | 1/4 | yes |
| interest-and-amortization | 4 | 1/4 | 0/4 | yes |
| interest-and-amortization | 5 | 4/4 | 0/4 | yes |
| interest-and-amortization | 6 | 3/4 | 0/4 | yes |
| interest-and-amortization | 7 | 3/4 | 0/4 | yes |
| money-arithmetic | 1 | 5/5 | 4/5 | yes |
| money-arithmetic | 2 | 4/4 | 0/4 | yes |
| money-arithmetic | 3 | 3/5 | 0/5 | yes |
| money-arithmetic | 4 | 3/4 | 1/4 | yes |
| money-arithmetic | 5 | 3/4 | 1/4 | yes |
| money-arithmetic | 6 | 4/4 | 3/4 | yes |
| money-arithmetic | 7 | 3/4 | 1/4 | yes |
| money-tests | 1 | 5/5 | 3/5 | yes |
| money-tests | 2 | 2/4 | 1/4 | yes |
| money-tests | 3 | 1/4 | 0/4 | yes |
| money-tests | 4 | 4/4 | 2/4 | yes |
| money-tests | 5 | 2/4 | 2/4 | yes |
| money-tests | 6 | 1/4 | 1/4 | yes |
| money-tests | 7 | 3/5 | 3/5 | yes |
| pii-and-card-data | 1 | 3/4 | 0/4 | yes |
| pii-and-card-data | 2 | 4/4 | 4/4 | yes |
| pii-and-card-data | 3 | 3/3 | 2/3 | yes |
| pii-and-card-data | 4 | 4/4 | 3/4 | yes |
| pii-and-card-data | 5 | 2/4 | 1/4 | yes |
| pii-and-card-data | 6 | 0/4 | 0/4 | yes |
| pii-and-card-data | 7 | 2/4 | 1/4 | yes |
| reconciliation | 1 | 5/5 | 3/5 | yes |
| reconciliation | 2 | 1/4 | 2/4 | yes |
| reconciliation | 3 | 2/4 | 0/4 | yes |
| reconciliation | 4 | 2/4 | 0/4 | yes |
| reconciliation | 5 | 3/4 | 2/4 | yes |
| reconciliation | 6 | 4/4 | 0/4 | yes |
| reconciliation | 7 | 4/4 | 0/4 | yes |
| transaction-classification | 1 | 3/5 | 1/5 | yes |
| transaction-classification | 2 | 2/4 | 0/4 | yes |
| transaction-classification | 3 | 3/3 | 2/3 | yes |
| transaction-classification | 4 | 2/4 | 0/4 | yes |
| transaction-classification | 5 | 2/3 | 2/3 | yes |
| transaction-classification | 6 | 2/4 | 0/4 | yes |
| transaction-classification | 7 | 1/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 0/5 | yes |
| webhook-handling | 2 | 2/4 | 0/4 | yes |
| webhook-handling | 3 | 4/4 | 1/4 | yes |
| webhook-handling | 4 | 4/4 | 0/4 | yes |
| webhook-handling | 5 | 0/4 | 0/4 | yes |
| webhook-handling | 6 | 3/4 | 0/4 | yes |
| webhook-handling | 7 | 2/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields above.
- `skills/<skill>.json`: one record per (eval, condition): the exact `claude` invocation, the subject's final answer, tokens, stop reason, wall time, the files it wrote with sha256, and the grader's verdict and evidence per expectation. Paths inside are relative to this folder.
- `raw/<skill>/<eval>-<condition>-1/`: `subject-transcript.txt` (Claude Code stream-json, project path replaced by `<project>`), `grader-transcript.txt`, and `files/` with what the subject wrote. Grader stdin (a copy of the transcript), stderr and the runner log are not included.

Raw transcripts and produced files (`raw/`) left the repository on 2026-11-08 so a plugin install stays small; they are attached to the GitHub release as `raw-20261108T053526Z-ee4f998.tar.gz`. The numbers in this file are unchanged.
