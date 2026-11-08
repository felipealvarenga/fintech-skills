# Money audit: payments module (`src/`, 8 files)

Date: 2026-11-08. Not a git repository, so there is no commit SHA. The review was manual (read every file in full).
The bundled lint (`money_lint.py`) was **not run** because shell access was unavailable. No vector suites were run.
No code was changed.

## Summary
11 findings: **4 critical, 6 high, 1 medium**. The module has no tests, no ledger, no audit trail and no reconciliation.

## Findings (ranked)
| # | Severity | Where | Rule | What happens | Fix | Test to add |
|---|----------|-------|------|--------------|-----|-------------|
| 1 | critical | src/boleto.py:6 | fintech-audit PAID_ON_ISSUE; idempotent-payments (state machine); brazil-payment-rails (boleto clears D+1) | Order is marked `paid` when the boleto is *issued*, not when it is paid. Goods or credit are released for unpaid boletos. | Leave order `pending`. Mark `paid` only from a verified PSP confirmation/return file. | Issue boleto -> order is `pending`; confirmation event -> `paid`. |
| 2 | critical | src/charges.py:11 | idempotent-payments 4 | `uuid4()` gives a new key on every call, so a timeout plus retry creates a second charge. | Derive key from the order id (and attempt scope), persist before calling Stripe. | Call `create_charge` twice for one order -> one PaymentIntent. |
| 3 | critical | src/models.py:8-9 | pii-and-card-data (no PAN storage, never store CVV) | `Card` holds the full card number and CVV. Storing the CVV is prohibited by PCI DSS. Any log or DB write of this object exposes both. | Remove `cvv`. Store only a processor token, last4 and brand. Use hosted fields. | Model has no `cvv`/PAN field; serialization of a card never contains 13-19 digit strings. |
| 4 | critical | src/webhooks.py:11-13 | webhook-handling (verify raw body) | Signature is checked against `json.dumps(request.get_json())`, not the raw bytes, so verification is unreliable (valid events may fail, and re-serialization defeats the signature's purpose). Secret `"whsec_x"` is hardcoded. No timestamp tolerance, no event-id dedupe, no state confirmation by API, no error handling (a bad signature raises a 500). | Use `request.get_data()`, load the secret from config, return 400 on failure, dedupe by `event.id`, store then acknowledge. | Tampered body -> 400; replayed event id -> processed once; reordered events do not regress state. |
| 5 | high | src/webhooks.py:12 | pii-and-card-data (allowlist logging); fintech-audit BODY_LOG | Whole payload is logged at INFO before verification, so unauthenticated input is logged and may carry personal data. | Log event id and type only, after verification. | Log capture after a webhook contains no payload fields. |
| 6 | high | src/wallet.py:5 | double-entry-ledger (balances derived from postings) | Balance is mutated in place. There is no overdraft check (it can go negative), no history, no idempotency, no audit record. | Post balanced journal entries with an external reference. Derive the balance from postings. | Concurrent pays cannot overdraw; same reference twice -> one posting; sum of postings equals the balance. |
| 7 | high | src/billing.py:8,12 | money-arithmetic (integer minor units, largest-remainder) | Amounts are floats and each part is rounded independently, so the parts may not sum to the total (cents lost or created). | Integer cents plus largest-remainder allocation. | Property test: `sum(split(total, ratios)) == total` for random inputs. |
| 8 | high | src/billing.py:16 | money-arithmetic | `int(float("19.99") * 100)` returns 1998 (truncation of a binary float). It is off by one cent for many inputs. | Parse with `Decimal`, validate the exponent, reject extra precision. | `to_cents("19.99") == 1999`, plus a sweep of 0.00-999.99. |
| 9 | high | src/documents.py:6 | brazil-payment-rails (CNPJ) | Accepts any 14 digits with no check-digit validation. Rejects alphanumeric CNPJ, which has been in effect since July 2026. | Validate the check digits and allow `[0-9A-Z]` in the first 12 characters. | Valid and invalid numeric and alphanumeric CNPJs from synthetic vectors. |
| 10 | high | src/charges.py:5 | money-arithmetic (rates) | The fee rate is a float (`0.035`). It is unused today, but it will drift when applied. | Use `Decimal` or basis points (350) with one named rounding policy. | Fee on a set of amounts matches frozen vectors. |
| 11 | medium | src/settlement.py:6 | brazil-payment-rails (business-day calendar); money-arithmetic | Uses naive local `datetime.now()` and a flat +1 calendar day. No weekends or holidays, no UTC, no injected clock. The `amount` parameter is unused. | Inject a clock, use UTC, apply a Brazilian business-day calendar. | Friday and pre-holiday dates roll to the next business day. |

## Checked and clean
- None. Every one of the 8 files has at least one finding.

## Not checked
- Lint script (`money_lint.py`) and vector suites: not run, no shell access.
- Reconciliation, accounting sync, transaction classification, audit trail, interest/amortization: there is no code for these in the module. Their absence is itself a gap: there is no audit trail on money mutations and no reconciler for pending charges.
- Tests: the repository contains none.
- Callers, configuration, database schema and migrations, deployment and secrets management: not in the repository.
- This is a correctness and operability review. It is not a security audit or a penetration test.

## Next three changes
1. Stop marking boleto orders paid on issue (`boleto.py:6`) and derive a stable idempotency key (`charges.py:11`). These two remove the largest direct money loss.
2. Delete `cvv` and the raw PAN from `Card`, and fix webhook verification (raw body, secret from config, dedupe).
3. Move to integer minor units (`billing.py`) and replace the in-place wallet balance update with ledger postings.
