# Evals

Every skill has `evals/evals.json` in the format used by Anthropic's `skill-creator`
(`skill_name`, `evals[]` with `id`, `prompt`, `expected_output`, `expectations`). Run them with
`skill-creator`'s `run_eval.py` against an agent with and without the skill, and grade the
transcripts against the expectations.

Every skill also ships **vectors**: language-neutral test cases as pytest files with a reference
implementation that proves they are satisfiable. Point the environment variable at your own
module to run them against your code.

| Skill | Vectors | Environment variable |
|---|---|---|
| money-arithmetic | `skills/money-arithmetic/evals/vectors/test_money.py` | `MONEY_SOLUTION` |
| double-entry-ledger | `skills/double-entry-ledger/evals/vectors/test_ledger.py` | `LEDGER_SOLUTION` |
| idempotent-payments | `skills/idempotent-payments/evals/vectors/test_idempotency.py` | `IDEMPOTENCY_SOLUTION` |
| webhook-handling | `skills/webhook-handling/evals/vectors/test_webhooks.py` | `WEBHOOK_SOLUTION` |
| reconciliation | `skills/reconciliation/evals/vectors/test_reconcile.py` | `RECON_SOLUTION` |
| accounting-sync | `skills/accounting-sync/evals/vectors/test_sync.py` | `SYNC_SOLUTION` |
| transaction-classification | `skills/transaction-classification/evals/vectors/test_classification.py` | `CLASSIFY_SOLUTION` |
| pii-and-card-data | `skills/pii-and-card-data/evals/vectors/test_pii.py` | `PII_SOLUTION` |
| audit-trail | `skills/audit-trail/evals/vectors/test_audit.py` | `AUDIT_SOLUTION` |
| interest-and-amortization | `skills/interest-and-amortization/evals/vectors/test_amortization.py` | `AMORT_SOLUTION` |
| brazil-payment-rails | `skills/brazil-payment-rails/evals/vectors/test_brazil.py` | `BRAZIL_SOLUTION` |
| money-tests | `skills/money-tests/evals/vectors/test_money_tests.py` | `MONEYTESTS_SOLUTION` |

Each skill has seven evals: three build prompts, three judgment prompts and at least one
adversarial prompt that asks for the unsafe thing (keep the floats, disable the signature check,
mark the order paid on issuance). Prompts that imply existing code list fixture files under
`evals/files/`, copied into the temporary project as `src/` before the session starts; greenfield
prompts say so. Expectations are written to be gradable from the transcript and the produced
files.

```sh
python -m pytest -q skills                                   # all vectors against the references
MONEY_SOLUTION=./src/money.py python -m pytest -q skills/money-arithmetic   # your implementation
```

TypeScript ports live beside the Python files (`*.test.ts` with `reference.ts`) and run with
`npm ci && npm run test:ts`; point `MONEY_SOLUTION_TS` (and the matching variable per skill) at
your module. Ports exist for money-arithmetic today; the remaining skills follow.
