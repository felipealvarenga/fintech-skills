# Changelog

Each entry names the skills commit it ships and the results folders that measured it.

## 0.1.0 - 2026-11-10

First release. Skills at `fa81209`.

- 13 skills: `fintech-audit` (the entry point, with `money_lint.py`), money-arithmetic, double-entry-ledger, idempotent-payments, webhook-handling, reconciliation, accounting-sync, transaction-classification, pii-and-card-data, audit-trail, interest-and-amortization, brazil-payment-rails, money-tests.
- Test vectors with a reference implementation for every skill (228 pytest tests) and TypeScript ports for money, webhooks, idempotency, ledger and Brazil (138 vitest tests). Both run in CI on every push.
- Seven development prompts and two held-out prompts per skill, run paired (with and without the skill) by `scripts/run_evals.py` with a blinded grader.
- Measured on this commit: `claude-sonnet-5-5` 81% of expectations with the skills, 24% without (held-out 70% / 24%); `claude-opus-5-5` 89% / 35% (held-out 81% / 31%). Method and per-skill numbers under `evals/results/`; raw transcripts are attached to the release.
- Installs as a Claude Code plugin, a Codex plugin, or with `npx skills add`.
- After the measured commit, one file under `skills/` changed: `fintech-audit/scripts/money_lint.py` skips symlinks, strips control characters from quoted lines and skips lines over 2000 characters (3b36f10). The eval sandbox has no shell, so the lint was not part of the measured setup; every SKILL.md is as measured.
