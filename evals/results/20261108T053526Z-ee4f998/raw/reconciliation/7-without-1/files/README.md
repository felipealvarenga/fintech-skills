# Reconciliation Dashboard

Matches ledger entries against bank statement lines and renders a static HTML dashboard.

```
PYTHONPATH=src python -m recon.dashboard sample/ledger.csv sample/bank.csv -o out.html
python -m pytest tests
```

CSV columns: `id,date(YYYY-MM-DD),amount[,reference,description]`.

Matching passes (each bank row used once): exact (reference + amount), fuzzy (amount + date within
`--tolerance` days, default 3), then amount mismatch (same reference, different amount).
Leftovers are listed as unmatched. All money uses `Decimal`.
