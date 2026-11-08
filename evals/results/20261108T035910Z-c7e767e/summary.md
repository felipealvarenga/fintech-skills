# Evaluation results, run 20261108T035910Z-c7e767e

Date 2026-11-08. Subject model `claude-sonnet-5-5`. Grader model `claude-sonnet-5-5`. Claude Code 2.1.319, headless.

**With the skill installed, 62.2% of expectations passed (230 of 370). Without it, 25.4% (94 of 370). Lift: 36.8 points.** 13 skills, 7 prompts each, one run per prompt per condition: 182 subject sessions, 182 grader sessions, 0 grader errors.

## Method

- Runner: `scripts/run_evals.py` at `c7e767e` (pull request #1), one invocation per skill, in this order: double-entry-ledger, brazil-payment-rails, fintech-audit, money-arithmetic, idempotent-payments, webhook-handling, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, money-tests. This folder combines the 13 run directories; `run_id` inside each `skills/<skill>.json` is that skill's own invocation.
- Skills measured: `c7e767e`, identical to `main` at `88e367c` except one line in `brazil-payment-rails/SKILL.md` that points at the TypeScript vectors.
- Install: `SKILL.md`, `references/` and `scripts/` copied to `.claude/skills/<name>/` in a fresh temporary project. Nothing under `evals/` is installed, so the subject cannot read the reference implementations or the expectations. The runner's worktree had `skills/*/evals/vectors` deleted as a second guard; `skills_dirty: true` in the per-skill files records that deletion and nothing else.
- fintech-audit installs all 13 skills in the with condition, because it delegates to the other twelve.
- Subject session: `claude -p --output-format json --model claude-sonnet-5-5 --max-turns 30 --tools Read,Write,Edit,Glob,Grep,Skill --setting-sources project --strict-mcp-config --permission-mode acceptEdits --permission-prompts none --no-session-persistence`, with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`. No Bash, no web tools, no MCP servers. Three built-in skills (design, doctor, plugin-authoring) still load in both conditions; none concerns money. The prompt is the eval prompt verbatim; fixture files listed in `evals.json` are copied to `src/` first.
- Grader session: same model, no tools. It receives the prompt, the expectations, the subject's final answer, the full subject transcript and every file the subject wrote, and returns one verdict with evidence per expectation. The verdicts and evidence are in `skills/<skill>.json`.
- Pass rate = passed expectations / (passed + failed). Each eval has 3 to 6 expectations; each skill has 27 to 30 per condition. The two conditions see the same prompts, fixtures and expectations.

## Pack level

| Condition | Pass rate | Passed | Failed | Subject tokens | Grader tokens | Wall seconds |
|---|---|---|---|---|---|---|
| with | 62.2% | 230 | 140 | 3,750,903 | 3,073,421 | 2874 |
| without | 25.4% | 94 | 276 | 2,196,139 | 1,768,940 | 1909 |

Tokens are the sums the Claude Code JSON result reports (input, output and cache tokens). Wall seconds add subject and grader sessions.

## Per skill

| Skill | With | Without | Lift (points) | Expectations per condition |
|---|---|---|---|---|
| reconciliation | 69.0% | 17.2% | 51.7 | 29 |
| webhook-handling | 58.6% | 13.8% | 44.8 | 29 |
| fintech-audit | 76.7% | 33.3% | 43.3 | 30 |
| transaction-classification | 55.6% | 14.8% | 40.7 | 27 |
| accounting-sync | 53.6% | 14.3% | 39.3 | 28 |
| idempotent-payments | 60.7% | 21.4% | 39.3 | 28 |
| money-arithmetic | 73.3% | 36.7% | 36.7 | 30 |
| double-entry-ledger | 75.0% | 39.3% | 35.7 | 28 |
| brazil-payment-rails | 51.7% | 17.2% | 34.5 | 29 |
| interest-and-amortization | 53.6% | 21.4% | 32.1 | 28 |
| money-tests | 66.7% | 36.7% | 30.0 | 30 |
| pii-and-card-data | 63.0% | 37.0% | 25.9 | 27 |
| audit-trail | 48.1% | 25.9% | 22.2 | 27 |

## Reading the numbers

- One run per prompt per condition. One eval flipping moves a skill's rate by 3 to 4 points, so per-skill differences under about 10 points are noise. The pack-level gap of 36.8 points over 370 expectations per condition is not.
- In 6 of 91 with-condition sessions the agent never opened the skill (audit-trail eval 3, audit-trail eval 5, interest-and-amortization eval 4, money-arithmetic eval 4, money-tests eval 4, pii-and-card-data eval 3). Those sessions count against the with condition as run. The only evals where with scored below without are idempotent-payments eval 4, interest-and-amortization eval 4, money-arithmetic eval 4; all are in that list, and all are adversarial prompts that tell the agent to keep floats, keep a display-only schedule or delete a flaky test. Making those prompts trigger the skill is the next change to the descriptions; it will be measured by a new run, not by editing this one.
- Cut rule stated before the run: a skill with under 10 points of lift on its own seven evals is folded into another or removed. The lowest lift is audit-trail at 22.2 points, so nothing was cut.
- The with condition used 1.7x the subject tokens of the without condition: it reads the skill and it writes the tests the skill asks for.
- The grader is a model reading transcripts against written expectations. Expectations were written before the run and are in each skill's `evals/evals.json`; a reader can re-grade any session from `raw/`.

## Per eval

| Skill | Eval | With | Without | Skill opened (with) |
|---|---|---|---|---|
| accounting-sync | 1 | 4/5 | 1/5 | yes |
| accounting-sync | 2 | 3/4 | 2/4 | yes |
| accounting-sync | 3 | 2/3 | 0/3 | yes |
| accounting-sync | 4 | 0/4 | 0/4 | yes |
| accounting-sync | 5 | 3/4 | 0/4 | yes |
| accounting-sync | 6 | 2/4 | 1/4 | yes |
| accounting-sync | 7 | 1/4 | 0/4 | yes |
| audit-trail | 1 | 3/4 | 1/4 | yes |
| audit-trail | 2 | 3/4 | 1/4 | yes |
| audit-trail | 3 | 2/4 | 2/4 | no |
| audit-trail | 4 | 2/4 | 1/4 | yes |
| audit-trail | 5 | 0/4 | 0/4 | no |
| audit-trail | 6 | 1/3 | 0/3 | yes |
| audit-trail | 7 | 2/4 | 2/4 | yes |
| brazil-payment-rails | 1 | 4/5 | 0/5 | yes |
| brazil-payment-rails | 2 | 2/4 | 0/4 | yes |
| brazil-payment-rails | 3 | 2/4 | 2/4 | yes |
| brazil-payment-rails | 4 | 1/4 | 0/4 | yes |
| brazil-payment-rails | 5 | 3/4 | 2/4 | yes |
| brazil-payment-rails | 6 | 2/4 | 1/4 | yes |
| brazil-payment-rails | 7 | 1/4 | 0/4 | yes |
| double-entry-ledger | 1 | 3/4 | 0/4 | yes |
| double-entry-ledger | 2 | 3/4 | 2/4 | yes |
| double-entry-ledger | 3 | 4/4 | 4/4 | yes |
| double-entry-ledger | 4 | 4/4 | 2/4 | yes |
| double-entry-ledger | 5 | 2/4 | 0/4 | yes |
| double-entry-ledger | 6 | 3/4 | 3/4 | yes |
| double-entry-ledger | 7 | 2/4 | 0/4 | yes |
| fintech-audit | 1 | 5/6 | 3/6 | yes |
| fintech-audit | 2 | 4/4 | 1/4 | yes |
| fintech-audit | 3 | 3/4 | 2/4 | yes |
| fintech-audit | 4 | 3/4 | 2/4 | yes |
| fintech-audit | 5 | 1/4 | 1/4 | yes |
| fintech-audit | 6 | 3/4 | 1/4 | yes |
| fintech-audit | 7 | 4/4 | 0/4 | yes |
| idempotent-payments | 1 | 4/5 | 0/5 | yes |
| idempotent-payments | 2 | 2/4 | 2/4 | yes |
| idempotent-payments | 3 | 3/4 | 1/4 | yes |
| idempotent-payments | 4 | 1/4 | 2/4 | yes |
| idempotent-payments | 5 | 3/4 | 0/4 | yes |
| idempotent-payments | 6 | 2/3 | 1/3 | yes |
| idempotent-payments | 7 | 2/4 | 0/4 | yes |
| interest-and-amortization | 1 | 5/5 | 3/5 | yes |
| interest-and-amortization | 2 | 1/3 | 1/3 | yes |
| interest-and-amortization | 3 | 2/4 | 1/4 | yes |
| interest-and-amortization | 4 | 0/4 | 1/4 | no |
| interest-and-amortization | 5 | 2/4 | 0/4 | yes |
| interest-and-amortization | 6 | 3/4 | 0/4 | yes |
| interest-and-amortization | 7 | 2/4 | 0/4 | yes |
| money-arithmetic | 1 | 5/5 | 4/5 | yes |
| money-arithmetic | 2 | 4/4 | 1/4 | yes |
| money-arithmetic | 3 | 3/5 | 0/5 | yes |
| money-arithmetic | 4 | 1/4 | 2/4 | no |
| money-arithmetic | 5 | 2/4 | 1/4 | yes |
| money-arithmetic | 6 | 4/4 | 2/4 | yes |
| money-arithmetic | 7 | 3/4 | 1/4 | yes |
| money-tests | 1 | 5/5 | 3/5 | yes |
| money-tests | 2 | 3/4 | 1/4 | yes |
| money-tests | 3 | 1/4 | 0/4 | yes |
| money-tests | 4 | 3/4 | 2/4 | no |
| money-tests | 5 | 2/4 | 2/4 | yes |
| money-tests | 6 | 2/4 | 0/4 | yes |
| money-tests | 7 | 4/5 | 3/5 | yes |
| pii-and-card-data | 1 | 3/4 | 0/4 | yes |
| pii-and-card-data | 2 | 4/4 | 4/4 | yes |
| pii-and-card-data | 3 | 2/3 | 1/3 | no |
| pii-and-card-data | 4 | 4/4 | 3/4 | yes |
| pii-and-card-data | 5 | 2/4 | 1/4 | yes |
| pii-and-card-data | 6 | 0/4 | 0/4 | yes |
| pii-and-card-data | 7 | 2/4 | 1/4 | yes |
| reconciliation | 1 | 5/5 | 3/5 | yes |
| reconciliation | 2 | 1/4 | 0/4 | yes |
| reconciliation | 3 | 1/4 | 0/4 | yes |
| reconciliation | 4 | 2/4 | 0/4 | yes |
| reconciliation | 5 | 3/4 | 2/4 | yes |
| reconciliation | 6 | 4/4 | 0/4 | yes |
| reconciliation | 7 | 4/4 | 0/4 | yes |
| transaction-classification | 1 | 3/5 | 1/5 | yes |
| transaction-classification | 2 | 2/4 | 0/4 | yes |
| transaction-classification | 3 | 3/3 | 2/3 | yes |
| transaction-classification | 4 | 2/4 | 0/4 | yes |
| transaction-classification | 5 | 2/3 | 0/3 | yes |
| transaction-classification | 6 | 2/4 | 0/4 | yes |
| transaction-classification | 7 | 1/4 | 1/4 | yes |
| webhook-handling | 1 | 4/5 | 0/5 | yes |
| webhook-handling | 2 | 3/4 | 0/4 | yes |
| webhook-handling | 3 | 4/4 | 2/4 | yes |
| webhook-handling | 4 | 2/4 | 1/4 | yes |
| webhook-handling | 5 | 0/4 | 0/4 | yes |
| webhook-handling | 6 | 2/4 | 0/4 | yes |
| webhook-handling | 7 | 2/4 | 1/4 | yes |

## Files

- `results.json`: pack, per-skill and per-eval numbers, plus the method fields above.
- `skills/<skill>.json`: one record per (eval, condition): the exact `claude` invocation, the subject's final answer, tokens, stop reason, wall time, the files it wrote with sha256, and the grader's verdict and evidence per expectation. Paths inside are relative to this folder.
- `raw/<skill>/<eval>-<condition>-1/`: `subject-transcript.txt` (Claude Code stream-json, project path replaced by `<project>`), `grader-transcript.txt`, and `files/` with what the subject wrote. Grader stdin (a copy of the transcript), stderr and the runner log are not included.

Raw transcripts and produced files (`raw/`) left the repository on 2026-11-08 so a plugin install stays small; they are attached to the GitHub release as `raw-20261108T035910Z-c7e767e.tar.gz`. The numbers in this file are unchanged.
