# fintech-skills

Fintech engineering skills for coding agents. Twelve skills that teach Claude Code, Codex,
Cursor, Copilot and any agent that reads `SKILL.md` how to handle money the way production
fintech systems do. Every skill ships with an eval. The numeric ones ship with test vectors that
run in CI.

[![ci](https://github.com/felipealvarenga/fintech-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/felipealvarenga/fintech-skills/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-111111)](LICENSE)

[Português](README.pt-BR.md)

## Why

Agents write payment code fast and wrong in the same ways people do: floats for amounts, a
balance column updated in place, a retry that charges twice, a webhook trusted as truth, a
reconciliation that hides breaks behind a tolerance. Each skill fixes one of those, with rules
that are testable, a review checklist, and the tests the change must include.

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

## Skills

| Skill | Use when | Vectors |
|---|---|---|
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Storing, adding, allocating, converting, rounding or formatting amounts | yes |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Any table that answers "how much does X hold or owe" | yes |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Creating, capturing, refunding or paying out money; calling a processor | |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receiving callbacks from processors, banks and PSPs | |
| [reconciliation](skills/reconciliation/SKILL.md) | Comparing ledger, processor and bank records of the same money | yes |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Pushing to or reading from QuickBooks, Xero, NetSuite, Omie, Conta Azul | |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizing transactions with rules, ML or an LLM, especially auto-posting | |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Collecting, logging, displaying or exporting personal, bank or card data | |
| [audit-trail](skills/audit-trail/SKILL.md) | Any mutation of money, limits, permissions or customer data; agent actions | |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Interest, installments, schedules, accruals, effective rates | yes |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, card installments, CPF and CNPJ, NF-e in Brazil | |
| [money-tests](skills/money-tests/SKILL.md) | Writing or reviewing tests for any of the above | |

Each `SKILL.md` has the same shape: when to use, numbered rules, how to apply, tests the change
must include, review checklist, anti-patterns with fixes, references.

## Evals

Every skill has `evals/evals.json` in the format used by Anthropic's `skill-creator`: prompts
an agent would receive, and expectations a grader checks in the transcript. Four skills also ship
vectors: pytest files with a reference implementation, runnable against your own code through
an environment variable. See [evals/README.md](evals/README.md).

Run paired evaluations with `python3 scripts/run_evals.py --skill money-arithmetic`.
For all skills, use `--all --budget 144`; the default budget is 80 sessions, including graders.
Use `--agent fake` to exercise the runner without a model. Real evals never run in CI.

```sh
python scripts/validate.py       # frontmatter, evals, manifest
python -m pytest -q              # vectors against the references
```

## Scope

These skills are engineering practice. They are not accounting, tax or legal advice; where a
rule depends on a jurisdiction (statutory rounding, tax codes, disclosed rates, retention
periods), the skill says so and keeps the engineering part. Vendor API mechanics belong to
vendor plugins: Stripe ships its own, Intuit ships `intuit-developer` and `quickbooks-labs`.
The skills link to them instead of duplicating them.

## How this was built

Written by Felipe Alvarenga from production work on credit, payments and accounting
integrations in Brazil and the US, drafted and iterated with Claude Code. Every rule was chosen
because its absence caused a real incident or a real month-end. The vectors run on every push;
the rubric evals are run by hand before each release.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One skill per folder, testable rules, three evals,
no vendor docs, no tax rules.

## License

MIT.
