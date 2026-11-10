# fintech-skills

Fintech engineering skills for coding agents: an audit entry point and twelve skills that teach
Claude Code, Codex, Cursor, Copilot and any agent that reads `SKILL.md` how to handle money the
way production fintech systems do. Every skill ships evals and test vectors that run in CI.

[![ci](https://github.com/felipealvarenga/fintech-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/felipealvarenga/fintech-skills/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-111111)](LICENSE)

[Português](README.pt-BR.md)

<!-- generated:headline -->
**Measured.** The same 91 prompts ran on `claude-sonnet-5-5` and `claude-opus-5-5` with and without the skills (skills at
`fa81209`), and `claude-sonnet-5-5` graded each transcript against expectations written before
the run. The score is the share of expectations the grader marked passed; the agent's code is read, not
executed. `claude-sonnet-5-5`: **81% with the skills, 24% without** (299 against 87 of 370); `claude-opus-5-5`: **89% with the skills, 35% without** (328 against 130 of 370). Per skill,
method and raw transcripts: [evals/results/20261108T180307Z-fa81209](evals/results/20261108T180307Z-fa81209/summary.md), [evals/results/20261109T103432Z-fa81209](evals/results/20261109T103432Z-fa81209/summary.md). Those prompts are development prompts: the skills were revised against
earlier runs' failures on them. On the held-out set, prompts in `evals/heldout/` that are never read when editing a skill: `claude-sonnet-5-5`: **70% with, 24% without** (73 against 25 of 105, [evals/results/20261108T194552Z-fa81209-heldout](evals/results/20261108T194552Z-fa81209-heldout/summary.md)); `claude-opus-5-5`: **81% with, 31% without** (85 against 33 of 105, [evals/results/20261109T110030Z-fa81209-heldout](evals/results/20261109T110030Z-fa81209-heldout/summary.md)); `claude-fable-5-2`: **88% with, 35% without** (92 against 37 of 105, [evals/results/20261110T031626Z-fa81209-heldout](evals/results/20261110T031626Z-fa81209-heldout/summary.md)).
<!-- /generated:headline -->

## Why

Agents write payment code fast and wrong in the same ways people do: floats for amounts, a
balance column updated in place, a retry that charges twice, a webhook trusted as truth, a
reconciliation that hides breaks behind a tolerance. Each skill fixes one of those, with rules
that are testable, a review checklist, and the tests the change must include.

What changes, in ten seconds:

```python
# split R$ 100,00 three ways                      # retry a charge after a timeout
- shares = [round(total * r, 2) for r in ratios]  - key = uuid4()            # new key per attempt
+ shares = allocate(10_000, [50, 30, 20])          + key = f"{tenant}:charge:{order_id}"
+ # -> [5000, 3000, 2000], sum always preserved    + # same key on every retry; the processor dedupes
```

The left column loses or invents cents on real ratios; the right column preserves the sum by
construction. The left key charges the customer twice after one timeout; with the right key the
retry is a duplicate the processor dedupes, for as long as the processor keeps the key. The skills
carry the other hundred rules like these, each with a test.

## Install

Claude Code:

```
/plugin marketplace add felipealvarenga/fintech-skills
/plugin install fintech-skills@felipealvarenga
```

Codex:

```sh
codex plugin marketplace add felipealvarenga/fintech-skills
codex plugin add fintech-skills@felipealvarenga
```

skills CLI (any agent that reads a `skills` folder):

```sh
npx skills add felipealvarenga/fintech-skills
```

Manual: copy `skills/<name>` into your project's `.claude/skills/` or `.agents/skills/`.

The skills are Markdown files under `skills/`; read one before you install it, since an installed skill
runs with your agent's permissions. The only code in the pack is the vectors you choose to run. To update:
`claude plugin update fintech-skills@felipealvarenga`, `codex plugin marketplace upgrade` then the
`codex plugin add` line again, or `npx skills update`.

Skills load when a session starts, so start a new session after installing. Then send
`Audit this repository's money code with fintech-skills.` on a repo you know: the agent should
load the `fintech-audit` skill first and report file, line, rule, fix and test. If the transcript
shows no skill read, start a new session. The lint the audit runs needs Python 3.10 or newer.

## Skills

Start with the audit. It runs a deterministic lint on your money code, confirms each lead by
reading, applies the checklists below and reports findings with file, line, rule, fix and test:

```
Audit this repository's money code with fintech-skills.
```

[Sample report](skills/fintech-audit/evals/sample-report.md) on the planted fixture: 12 findings
in 8 files, 4 critical, each with file, line, rule, fix and test. Sonnet 5.5, 7 turns, USD 0.21.

<!-- generated:skills-table -->
| Skill | Use when | `claude-sonnet-5-5` with / without | `claude-opus-5-5` with / without | `claude-fable-5-2` with / without, held-out | Vectors |
|---|---|---|---|---|---|
| [fintech-audit](skills/fintech-audit/SKILL.md)† | Auditing a repo or a PR that touches money; the entry point | 77% / 33% | 83% / 40% | 100% / 88% | py |
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Storing, adding, allocating, converting, rounding or formatting amounts | 83% / 33% | 90% / 47% | 100% / 62% | py, ts |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Any table that answers "how much does X hold or owe" | 82% / 25% | 93% / 39% | 100% / 38% | py, ts |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Creating, capturing, refunding or paying out money; calling a processor | 86% / 21% | 100% / 36% | 75% / 25% | py, ts |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receiving callbacks from processors, banks and PSPs | 86% / 7% | 86% / 28% | 100% / 22% | py, ts |
| [reconciliation](skills/reconciliation/SKILL.md) | Comparing ledger, processor and bank records of the same money | 72% / 10% | 86% / 24% | 88% / 25% | py |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Pushing to or reading from QuickBooks, Xero, NetSuite, Omie, Conta Azul | 68% / 21% | 86% / 29% | 88% / 38% | py |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizing transactions with rules, ML or an LLM, especially auto-posting | 100% / 22% | 96% / 26% | 100% / 25% | py |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Collecting, logging, displaying or exporting personal, bank or card data | 63% / 37% | 81% / 44% | 75% / 62% | py |
| [audit-trail](skills/audit-trail/SKILL.md) | Any mutation of money, limits, permissions or customer data; agent actions | 74% / 26% | 85% / 33% | 88% / 38% | py |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Interest, installments, schedules, accruals, effective rates | 71% / 18% | 79% / 32% | 75% / 38% | py |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, card installments, CPF and CNPJ, NF-e in Brazil | 90% / 21% | 86% / 31% | 100% / 0% | py, ts |
| [money-tests](skills/money-tests/SKILL.md) | Writing or reviewing tests for any of the above | 97% / 30% | 100% / 47% | 50% / 0% | py |

One run per prompt. A cell of about 28 expectations carries up to about ±14 points (95% Wilson interval); the pack-level numbers carry up to about ±4. The `claude-fable-5-2` column is its held-out run (two prompts per skill, cells of about 8 expectations, about ±22 points each); read it at the pack level: 88% with, 35% without. † fintech-audit was measured without the lint it runs: the eval sandbox has no shell, so its row and the sample report (produced with a shell) are not the same setup.
<!-- /generated:skills-table -->

Each `SKILL.md` has the same shape: when to use, numbered rules, how to apply, what to do when the
request pushes back, the tests the change must include, a review checklist, anti-patterns with
fixes, references. The table above is rendered from the skills' frontmatter and the latest run.

## Evals

Every skill has `evals/evals.json` (prompts an agent would receive, and expectations a grader
checks in the transcript) and `evals/vectors/` (pytest and vitest files with a reference
implementation, runnable against your own code through an environment variable). A graded run
sends the same prompts with and without the skill, grades both, and lands in its own folder under
`evals/results/` with the models, the git sha, every transcript and every file the agent wrote.
Old folders are never edited. Method and flags: [evals/README.md](evals/README.md).

<!-- generated:runs -->
| Run | Skills at | Prompts | Subject | With | Without | Lift (points) |
|---|---|---|---|---|---|---|
| [20261108T035910Z-c7e767e](evals/results/20261108T035910Z-c7e767e/summary.md) | `c7e767e` | development | `claude-sonnet-5-5` | 62% | 25% | 36.8 |
| [20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md) | `ee4f998` | development | `claude-sonnet-5-5` | 72% | 27% | 45.4 |
| [20261108T143507Z-ae8adc1](evals/results/20261108T143507Z-ae8adc1/summary.md) | `ae8adc1` | development | `claude-sonnet-5-5` | 78% | 26% | 52.4 |
| [20261108T180307Z-fa81209](evals/results/20261108T180307Z-fa81209/summary.md) | `fa81209` | development | `claude-sonnet-5-5` | 81% | 24% | 57.3 |
| [20261108T194552Z-fa81209-heldout](evals/results/20261108T194552Z-fa81209-heldout/summary.md) | `fa81209` | held-out | `claude-sonnet-5-5` | 70% | 24% | 45.7 |
| [20261109T103432Z-fa81209](evals/results/20261109T103432Z-fa81209/summary.md) | `fa81209` | development | `claude-opus-5-5` | 89% | 35% | 53.5 |
| [20261109T110030Z-fa81209-heldout](evals/results/20261109T110030Z-fa81209-heldout/summary.md) | `fa81209` | held-out | `claude-opus-5-5` | 81% | 31% | 49.5 |
| [20261110T031626Z-fa81209-heldout](evals/results/20261110T031626Z-fa81209-heldout/summary.md) | `fa81209` | held-out | `claude-fable-5-2` | 88% | 35% | 52.4 |

In 2 of the 91 with-skill sessions of the `claude-sonnet-5-5` run on `fa81209` the agent never opened the skill; those sessions count against the skills. In all 91 with-skill sessions of the `claude-opus-5-5` run on `fa81209` the agent opened the skill.
<!-- /generated:runs -->

```sh
python scripts/validate.py   # frontmatter, evals, manifest, generated docs
python -m pytest -q          # vectors against the references, runner tests
npm ci && npm run test:ts    # TypeScript vectors
```

## Scope

These skills are engineering practice. They are not accounting, tax or legal advice; where a
rule depends on a jurisdiction (statutory rounding, tax codes, disclosed rates, retention
periods), the skill says so and keeps the engineering part. Vendor API mechanics belong to
vendor plugins: Stripe ships its own, Intuit ships `intuit-developer` and `quickbooks-labs`.
The skills link to them instead of duplicating them.

## How this was built

Written by Felipe Alvarenga from production work on credit, payments and accounting
integrations in Brazil and the US, drafted and iterated with Claude Code. The vectors run on every
push. The graded evals run before each release and each run's failures change the skills for the
next; the run summaries record what changed and why.

<!-- generated:cut-rule -->
The cut rule stated before the first run: a skill that does not move its own evals by at least 10 points
is folded or removed. In the `claude-sonnet-5-5` run on `fa81209` the lowest lift was 25.9 points (pii-and-card-data) and the highest 79.3 (webhook-handling); in the `claude-opus-5-5` run on `fa81209` the lowest lift was 37.0 points (pii-and-card-data) and the highest 70.4 (transaction-classification).
One cell's noise is about ±14 points, so the rule is applied over repeated runs, not one.
<!-- /generated:cut-rule -->

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One skill per folder, testable rules, at least six evals
with one adversarial, vectors with a reference implementation, no vendor docs, no tax rules.

## License

MIT.
