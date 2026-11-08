# fintech-skills

Fintech engineering skills for coding agents: an audit entry point and twelve skills that teach
Claude Code, Codex, Cursor, Copilot and any agent that reads `SKILL.md` how to handle money the
way production fintech systems do. Every skill ships evals and test vectors that run in CI.

[![ci](https://github.com/felipealvarenga/fintech-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/felipealvarenga/fintech-skills/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-111111)](LICENSE)

[Português](README.pt-BR.md)

<!-- generated:headline -->
**Measured.** The same 91 prompts ran on `claude-sonnet-5-5` with and without the skills (skills at
`ee4f998`), and a separate session of the same model graded each transcript against expectations written before
the run. The score is the share of expectations the grader marked passed; the agent's code is read, not
executed. **With the skills, 72%. Without them, 27%** (267 against 99 of 370). Per skill,
method and raw transcripts: [evals/results/20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md).
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

Skills load when a session starts, so start a new session after installing. Then send
`Audit this repository's money code with fintech-skills.` on a repo you know: the first tool call
is the `fintech-audit` skill and the report lists file, line, rule, fix and test. The lint the
audit runs needs Python 3.10 or newer on the machine.

## Skills

Start with the audit. It runs a deterministic lint on your money code, confirms each lead by
reading, applies the checklists below and reports findings with file, line, rule, fix and test:

```
Audit this repository's money code with fintech-skills.
```

[Sample report](skills/fintech-audit/evals/sample-report.md) on the planted fixture: 12 findings
in 8 files, 4 critical, each with file, line, rule, fix and test. Sonnet 5.5, 7 turns, USD 0.21.

<!-- generated:skills-table -->
| Skill | Use when | With / without | Vectors |
|---|---|---|---|
| [fintech-audit](skills/fintech-audit/SKILL.md) | Auditing a repo or a PR that touches money; the entry point | 77% / 50% | py |
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Storing, adding, allocating, converting, rounding or formatting amounts | 83% / 33% | py, ts |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Any table that answers "how much does X hold or owe" | 82% / 32% | py, ts |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Creating, capturing, refunding or paying out money; calling a processor | 93% / 25% | py, ts |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receiving callbacks from processors, banks and PSPs | 69% / 7% | py, ts |
| [reconciliation](skills/reconciliation/SKILL.md) | Comparing ledger, processor and bank records of the same money | 72% / 24% | py |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Pushing to or reading from QuickBooks, Xero, NetSuite, Omie, Conta Azul | 64% / 14% | py |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizing transactions with rules, ML or an LLM, especially auto-posting | 56% / 22% | py |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Collecting, logging, displaying or exporting personal, bank or card data | 67% / 41% | py |
| [audit-trail](skills/audit-trail/SKILL.md) | Any mutation of money, limits, permissions or customer data; agent actions | 78% / 22% | py |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Interest, installments, schedules, accruals, effective rates | 68% / 18% | py |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, card installments, CPF and CNPJ, NF-e in Brazil | 69% / 17% | py, ts |
| [money-tests](skills/money-tests/SKILL.md) | Writing or reviewing tests for any of the above | 60% / 40% | py |
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
| Run | Skills at | Subject | With | Without | Lift (points) |
|---|---|---|---|---|---|
| [20261108T035910Z-c7e767e](evals/results/20261108T035910Z-c7e767e/summary.md) | `c7e767e` | `claude-sonnet-5-5` | 62% | 25% | 36.8 |
| [20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md) | `ee4f998` | `claude-sonnet-5-5` | 72% | 27% | 45.4 |

In 1 of the 91 with-skill sessions of the latest run the agent never opened the skill; that session counts against the skills.
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
A skill that does not move its own evals by at least 10 points gets folded or removed; in the latest
run the lowest lift was 20.0 points (money-tests) and the highest 67.9 (idempotent-payments).
<!-- /generated:cut-rule -->

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One skill per folder, testable rules, at least six evals
with one adversarial, vectors with a reference implementation, no vendor docs, no tax rules.

## License

MIT.
