# Evaluation results, run 20261108T143507Z-ae8adc1

Date 2026-11-08, 14:35 to 16:24 UTC. Subject model `claude-sonnet-5-5`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless.

**With the skill installed, 78.1% of expectations passed (289 of 370). Without it, 25.7% (95 of 370). Lift: 52.4 points.** 13 skills, 7 prompts each, one run per prompt per condition: 182 subject sessions, 182 grader sessions, 0 grader errors, 0 max-turn stops.

## Changes since the previous run

The previous run, [20261108T053526Z-ee4f998](../20261108T053526Z-ee4f998/summary.md), measured 72.2% with and 26.8% without (267 and 99 of 370) on the skills at `ee4f998`. Its with-condition failures clustered in three skills: webhook-handling eval 5 scored 0 of 4 with the skill opened (the agent took "we trust Stripe, no API call" as permission and left dedupe and ordering out "since you didn't ask"), and transaction-classification and money-tests carried 12 failures each, where the agent described calibration, correction capture, a fake processor or a mutation run instead of writing them.

Commit `eadbaa9` answered those three skills. webhook-handling: a pushback table (no API call, latency, allowlist, later), the API fetch placed in the worker, a minimal state machine when the repository has none, replay with an audit table that skips already processed events, metrics in the same change, three more required tests. transaction-classification: a holdout file and `calibrate.py` even with no labels, `thresholds.json` instead of a placeholder constant, correction capture as three functions in the first change, a pushback table, four more required tests. money-tests: the kill-rate definition and CI gate with the likely survivors named when the tool cannot run, fake processor script entries, the clock injected in helpers too, the scheduled re-record job, a pushback table, three more required tests. The shared conflict paragraph in all 13 skills now says that an instruction to skip a step is the conflict, not permission, and that a review returns the rewritten tests.

Three eval changes, stated so the runs can be compared honestly:

- `transaction-classification` eval 7: the fixture `holdout.jsonl` grew from 3 to 40 labeled rows. With 3 rows the agent refused to compare models in both conditions.
- `transaction-classification` eval 7, expectations 1 and 2, reworded after reading the run 2 verdicts, because the subject session has no shell and no network and so can never "run both models": from "Runs both models on the same held-out set" and "Reports precision, recall and coverage per class, plus cost and latency" to "Evaluates both models on the same held-out set: runs the comparison when a model client is available, otherwise delivers the runnable harness and the table it fills" and "Lays out precision, recall and coverage per class, plus cost and latency, for both models side by side".
- `money-tests` eval 6, expectations 3 and 4, reworded for the same reason (the subject cannot run mutmut): from "Sets a threshold (around 80%) and reports the number in the pull request" and "Lists surviving mutants as missing assertions to add" to "Sets a threshold (around 80%) enforced by a CI gate and puts the kill rate in the pull request description, or the run command and the slot for the number when the tool could not run in the session" and "Names surviving or likely-surviving mutants in the module, each with the assertion that kills it".

Both conditions are graded on the new wording. Those two evals (8 expectations per condition) are not comparable with the previous runs; the other 89 prompts, fixtures and expectations are identical to run 2. No other prompt or expectation changed.

A first attempt at this run (13:06 to 14:33 UTC, five skills completed) was discarded before any of its numbers were compared: the runner as merged in pull request #1 installed `evals/vectors/`, whose `reference.py` and `reference.ts` are the answers to the vectors the skill asks for, into the with condition. Runs 1 and 2 had avoided that by deleting the vectors from the worktree by hand. The runner now excludes everything under `evals/` (`ae8adc1`, with a test), and this run started from scratch on that commit. The discarded attempt is not published.

## Method

- Runner: `scripts/run_evals.py` at `ae8adc1` on `main`: pull request #1, the fenced-verdict parser fix (`85492a1`) and the install rule that excludes everything under `evals/` (`ae8adc1`). One invocation per skill, in this order: double-entry-ledger, brazil-payment-rails, fintech-audit, money-arithmetic, idempotent-payments, webhook-handling, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, money-tests, 14:35 to 16:24 UTC. This folder combines the 13 run directories; `run_id` inside each `skills/<skill>.json` is that skill's own invocation.
- Skills measured: `ae8adc1`, the head of `main` at the time of the run; the skill folders are byte-identical to `eadbaa9`, the commit that changed them (the two commits in between touched only the runner and its docs).
- Install: `SKILL.md`, `references/` and `scripts/` copied to `.claude/skills/<name>/` in a fresh temporary project. Nothing under `evals/` is installed, by the runner's own rule, so the subject cannot read the reference implementations or the expectations; `installed_paths` in each `skills/<skill>.json` lists exactly what the subject could read. `skills_dirty: false`: the worktree was a clean checkout of `main`.
- fintech-audit installs all 13 skills in the with condition, because it delegates to the other twelve.
- Subject session: `claude -p --output-format json --model claude-sonnet-5-5 --max-turns 30 --tools Read,Write,Edit,Glob,Grep,Skill --setting-sources project --strict-mcp-config --permission-mode acceptEdits --permission-prompts none --no-session-persistence`, with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`. No Bash, no web tools, no MCP servers. The prompt is the eval prompt verbatim; fixture files listed in `evals.json` are copied to `src/` first.
- Grader session: same model, no tools. It receives the prompt, the expectations, the subject's final answer, the full subject transcript and every file the subject wrote, and returns one verdict with evidence per expectation. The verdicts and evidence are in `skills/<skill>.json`.
- Pass rate = passed expectations / (passed + failed). Each eval has 3 to 6 expectations; each skill has 27 to 30 per condition. The two conditions see the same prompts, fixtures and expectations.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 78.1% | 289 | 81 | 4,548,115 | 4,249,471 | 4347 |
| without | 25.7% | 95 | 275 | 2,244,132 | 1,785,564 | 2200 |

Tokens are the sums the Claude Code JSON result reports (input, output and cache tokens). Wall seconds add subject and grader sessions.

## Per skill

| Skill | With | Without | Lift (points) | Previous run with / without | Expectations per condition |
|---|---|---|---|---|---|
| transaction-classification | 100.0% | 18.5% | 81.5 | 55.6% / 22.2% | 27 |
| webhook-handling | 86.2% | 6.9% | 79.3 | 69.0% / 6.9% | 29 |
| accounting-sync | 78.6% | 14.3% | 64.3 | 64.3% / 14.3% | 28 |
| idempotent-payments | 85.7% | 21.4% | 64.3 | 92.9% / 25.0% | 28 |
| reconciliation | 75.9% | 17.2% | 58.6 | 72.4% / 24.1% | 29 |
| money-tests | 93.3% | 43.3% | 50.0 | 60.0% / 40.0% | 30 |
| audit-trail | 70.4% | 22.2% | 48.1 | 77.8% / 22.2% | 27 |
| money-arithmetic | 83.3% | 36.7% | 46.7 | 83.3% / 33.3% | 30 |
| interest-and-amortization | 67.9% | 21.4% | 46.4 | 67.9% / 17.9% | 28 |
| fintech-audit | 76.7% | 36.7% | 40.0 | 76.7% / 50.0% | 30 |
| double-entry-ledger | 78.6% | 39.3% | 39.3 | 82.1% / 32.1% | 28 |
| brazil-payment-rails | 55.2% | 17.2% | 37.9 | 69.0% / 17.2% | 29 |
| pii-and-card-data | 63.0% | 37.0% | 25.9 | 66.7% / 40.7% | 27 |

## The three targeted skills

| Skill | Run 2 with / without | Run 3 with / without | With-condition failures, run 2 to run 3 |
|---|---|---|---|
| webhook-handling | 69.0% / 6.9% | 86.2% / 6.9% | 9 to 4 |
| transaction-classification | 55.6% / 22.2% | 100.0% / 18.5% | 12 to 0 |
| money-tests | 60.0% / 40.0% | 93.3% / 43.3% | 12 to 2 |

webhook-handling eval 5 ("we trust Stripe, no API call"): with 0/4 in run 2, 0/4 in run 3; without 0/4 and 0/4.

## Reading the numbers

- One run per prompt per condition. The without condition is the noise gauge: apart from the two evals above, nothing it sees changed between the runs, and it moved from 26.8% to 25.7% at pack level, but up to 13 points for one skill (fintech-audit). Single-skill moves of that size are within run-to-run variation. The pack-level gap of 52.4 points over 370 expectations per condition is many times that variation, and the with condition moved 5.9 points between the runs; with one run per prompt and expectations that are correlated within a response, no confidence interval is claimed. Repeated paired runs are the way to get one.
- In 1 of 91 with-condition sessions the agent never opened the skill (brazil-payment-rails eval 4); the previous run had 1 (accounting-sync eval 4). Such a session counts against the with condition as run.
- Evals where with scored below without: brazil-payment-rails eval 2, brazil-payment-rails eval 5, pii-and-card-data eval 2 (skill opened: yes, yes, yes). The previous run had 2 (brazil-payment-rails eval 5, reconciliation eval 2).
- Cut rule stated before the first run: a skill with under 10 points of lift on its own seven evals is folded into another or removed. The lowest lift is pii-and-card-data at 25.9 points, so nothing was cut.
- The with condition used 2.0x the subject tokens of the without condition: it reads the skill and it writes the tests the skill asks for.
- The remaining with-condition failures are largest in brazil-payment-rails (13) and pii-and-card-data (10). They will be measured by a new run, not by editing this one.
- The grader is a model reading transcripts against written expectations. Expectations are in each skill's `evals/evals.json`; the two reworded ones are quoted above with their old text; a reader can re-grade any session from `raw/`.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 5/5 | 1/5 | yes |
| accounting-sync | 2 | 4/4 | 2/4 | yes |
| accounting-sync | 3 | 2/3 | 0/3 | yes |
| accounting-sync | 4 | 2/4 | 0/4 | yes |
| accounting-sync | 5 | 4/4 | 0/4 | yes |
| accounting-sync | 6 | 2/4 | 1/4 | yes |
| accounting-sync | 7 | 3/4 | 0/4 | yes |
| audit-trail | 1 | 4/4 | 1/4 | yes |
| audit-trail | 2 | 3/4 | 0/4 | yes |
| audit-trail | 3 | 3/4 | 2/4 | yes |
| audit-trail | 4 | 2/4 | 1/4 | yes |
| audit-trail | 5 | 2/4 | 0/4 | yes |
| audit-trail | 6 | 2/3 | 0/3 | yes |
| audit-trail | 7 | 3/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 5/5 | 0/5 | yes |
| brazil-payment-rails | 2 | 1/4 | 2/4 | yes |
| brazil-payment-rails | 3 | 4/4 | 0/4 | yes |
| brazil-payment-rails | 4 | 0/4 | 0/4 | no |
| brazil-payment-rails | 5 | 1/4 | 2/4 | yes |
| brazil-payment-rails | 6 | 4/4 | 1/4 | yes |
| brazil-payment-rails | 7 | 1/4 | 0/4 | yes |
| double-entry-ledger | 1 | 4/4 | 0/4 | yes |
| double-entry-ledger | 2 | 3/4 | 3/4 | yes |
| double-entry-ledger | 3 | 4/4 | 4/4 | yes |
| double-entry-ledger | 4 | 4/4 | 1/4 | yes |
| double-entry-ledger | 5 | 1/4 | 0/4 | yes |
| double-entry-ledger | 6 | 3/4 | 3/4 | yes |
| double-entry-ledger | 7 | 3/4 | 0/4 | yes |
| fintech-audit | 1 | 5/6 | 3/6 | yes |
| fintech-audit | 2 | 4/4 | 2/4 | yes |
| fintech-audit | 3 | 3/4 | 1/4 | yes |
| fintech-audit | 4 | 3/4 | 2/4 | yes |
| fintech-audit | 5 | 1/4 | 1/4 | yes |
| fintech-audit | 6 | 4/4 | 2/4 | yes |
| fintech-audit | 7 | 3/4 | 0/4 | yes |
| idempotent-payments | 1 | 5/5 | 1/5 | yes |
| idempotent-payments | 2 | 3/4 | 2/4 | yes |
| idempotent-payments | 3 | 4/4 | 1/4 | yes |
| idempotent-payments | 4 | 2/4 | 1/4 | yes |
| idempotent-payments | 5 | 4/4 | 0/4 | yes |
| idempotent-payments | 6 | 3/3 | 1/3 | yes |
| idempotent-payments | 7 | 3/4 | 0/4 | yes |
| interest-and-amortization | 1 | 5/5 | 3/5 | yes |
| interest-and-amortization | 2 | 2/3 | 1/3 | yes |
| interest-and-amortization | 3 | 2/4 | 1/4 | yes |
| interest-and-amortization | 4 | 1/4 | 1/4 | yes |
| interest-and-amortization | 5 | 4/4 | 0/4 | yes |
| interest-and-amortization | 6 | 2/4 | 0/4 | yes |
| interest-and-amortization | 7 | 3/4 | 0/4 | yes |
| money-arithmetic | 1 | 5/5 | 4/5 | yes |
| money-arithmetic | 2 | 3/4 | 2/4 | yes |
| money-arithmetic | 3 | 4/5 | 0/5 | yes |
| money-arithmetic | 4 | 3/4 | 1/4 | yes |
| money-arithmetic | 5 | 3/4 | 1/4 | yes |
| money-arithmetic | 6 | 4/4 | 2/4 | yes |
| money-arithmetic | 7 | 3/4 | 1/4 | yes |
| money-tests | 1 | 5/5 | 3/5 | yes |
| money-tests | 2 | 4/4 | 1/4 | yes |
| money-tests | 3 | 3/4 | 0/4 | yes |
| money-tests | 4 | 4/4 | 3/4 | yes |
| money-tests | 5 | 3/4 | 2/4 | yes |
| money-tests | 6 | 4/4 | 1/4 | yes |
| money-tests | 7 | 5/5 | 3/5 | yes |
| pii-and-card-data | 1 | 3/4 | 0/4 | yes |
| pii-and-card-data | 2 | 3/4 | 4/4 | yes |
| pii-and-card-data | 3 | 3/3 | 2/3 | yes |
| pii-and-card-data | 4 | 4/4 | 3/4 | yes |
| pii-and-card-data | 5 | 2/4 | 1/4 | yes |
| pii-and-card-data | 6 | 0/4 | 0/4 | yes |
| pii-and-card-data | 7 | 2/4 | 0/4 | yes |
| reconciliation | 1 | 5/5 | 3/5 | yes |
| reconciliation | 2 | 2/4 | 0/4 | yes |
| reconciliation | 3 | 2/4 | 0/4 | yes |
| reconciliation | 4 | 1/4 | 0/4 | yes |
| reconciliation | 5 | 4/4 | 2/4 | yes |
| reconciliation | 6 | 4/4 | 0/4 | yes |
| reconciliation | 7 | 4/4 | 0/4 | yes |
| transaction-classification | 1 | 5/5 | 1/5 | yes |
| transaction-classification | 2 | 4/4 | 0/4 | yes |
| transaction-classification | 3 | 3/3 | 2/3 | yes |
| transaction-classification | 4 | 4/4 | 0/4 | yes |
| transaction-classification | 5 | 3/3 | 1/3 | yes |
| transaction-classification | 6 | 4/4 | 0/4 | yes |
| transaction-classification | 7 | 4/4 | 1/4 | yes |
| webhook-handling | 1 | 5/5 | 0/5 | yes |
| webhook-handling | 2 | 4/4 | 0/4 | yes |
| webhook-handling | 3 | 4/4 | 1/4 | yes |
| webhook-handling | 4 | 4/4 | 1/4 | yes |
| webhook-handling | 5 | 0/4 | 0/4 | yes |
| webhook-handling | 6 | 4/4 | 0/4 | yes |
| webhook-handling | 7 | 4/4 | 0/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields above.
- `skills/<skill>.json`: one record per (eval, condition): the exact `claude` invocation, the subject's final answer, tokens, stop reason, wall time, the files it wrote with sha256, and the grader's verdict and evidence per expectation. Paths inside are relative to this folder.
- `raw-20261108T143507Z-ae8adc1.tar.gz`, attached to the GitHub release: `raw/<skill>/<eval>-<condition>-1/` with `subject-transcript.txt` (Claude Code stream-json, project path replaced by `<project>`), `grader-transcript.txt`, and `files/` with what the subject wrote. Grader stdin (a copy of the transcript), stderr and the runner log are not included.
