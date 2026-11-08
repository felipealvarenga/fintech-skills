# Evals

Every skill has `evals/evals.json` in the format used by Anthropic's `skill-creator`
(`skill_name`, `evals[]` with `id`, `prompt`, `expected_output`, `expectations`). Run them with
`skill-creator`'s `run_eval.py` against an agent with and without the skill, and grade the
transcripts against the expectations.

Four skills also ship **vectors**: language-neutral test cases as pytest files with a reference
implementation that proves they are satisfiable.

| Skill | Vectors | Environment variable |
|---|---|---|
| money-arithmetic | `skills/money-arithmetic/evals/vectors/test_money.py` | `MONEY_SOLUTION` |
| double-entry-ledger | `skills/double-entry-ledger/evals/vectors/test_ledger.py` | `LEDGER_SOLUTION` |
| interest-and-amortization | `skills/interest-and-amortization/evals/vectors/test_amortization.py` | `AMORT_SOLUTION` |
| reconciliation | `skills/reconciliation/evals/vectors/test_reconcile.py` | `RECON_SOLUTION` |

```sh
python -m pytest -q skills                                   # all vectors against the references
MONEY_SOLUTION=./src/money.py python -m pytest -q skills/money-arithmetic   # your implementation
```

The vectors are Python today. The cases are listed in each test file so they can be ported to
another language by hand.
