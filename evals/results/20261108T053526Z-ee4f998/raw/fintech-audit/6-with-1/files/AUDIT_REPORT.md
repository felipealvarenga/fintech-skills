# Money audit: payments module (`src/`), not a git repo so no sha, 2026-11-08

Scope: 8 files, 74 lines of Python, read in full. Every finding below comes from reading the code.
The bundled lint script and the vector suites were NOT run (see "Not checked").

## Findings (ranked)

| # | Severity | Where | Rule | What happens | Fix | Test to add |
|---|----------|-------|------|--------------|-----|-------------|
| 1 | critical | src/charges.py:11 | idempotent-payments (caller-chosen key) | `uuid4()` makes a new key per call. A timeout plus retry creates a second PaymentIntent, so the customer is charged twice. | Derive the key from the order id (and attempt/purpose), and persist the intent before the call. | Call `create_charge` twice for one order: exactly one PaymentIntent is created. |
| 2 | critical | src/boleto.py:6 | brazil-payment-rails (boleto) | The order is set to `paid` when the boleto is issued, not when the bank confirms payment. Unpaid orders are fulfilled. | Leave the order `pending`. Mark it paid only from a confirmed settlement or webhook event. | After `generate_boleto`, `order.status == "pending"`. |
| 3 | critical | src/models.py:8-9 | pii-and-card-data | `Card` holds the full PAN and the CVV. Storing the CVV is prohibited by PCI DSS, and the PAN should not be in your systems at all. | Remove `cvv`. Store a processor token plus brand/last4/expiry. Use hosted fields. | The `Card` model has no `cvv` or full `card_number` field. |
| 4 | critical | src/webhooks.py:11-13 | webhook-handling (raw body) | The signature is verified against `json.dumps(payload)`, a re-serialised body that will not match the signed bytes, so valid events fail. If verification were loosened to make them pass, forged events would be accepted. The secret `"whsec_x"` is hardcoded. | Verify on `request.get_data()` and read the secret from config. | A valid signature on the raw body is accepted. A tampered body and a stale timestamp are rejected. |
| 5 | high | src/webhooks.py:12 | pii-and-card-data / webhook-handling | The full webhook payload is logged. It can contain customer and payment data. | Log only the event id and type, using an allowlist. | The log output for a sample event contains no payload fields. |
| 6 | high | src/webhooks.py:10-14 | webhook-handling | There is no dedupe by event id, no store-then-acknowledge, and no state confirmation by API. Retried events would be processed twice once handling is added. | Add a unique index on event id, persist the event, process it asynchronously, and confirm state by API. | Deliver the same event twice: one effect. |
| 7 | high | src/wallet.py:5 | double-entry-ledger | `UPDATE ... SET balance = balance - %s` has no overdraft guard and no journal. It is not auditable or reversible, and concurrent debits can go negative. | Append balanced postings and derive the balance. At minimum, guard with `WHERE balance >= %s`. | A debit larger than the balance is rejected. A concurrent double-debit leaves the balance at or above 0. |
| 8 | high | src/billing.py:8,12 | money-arithmetic | Amounts are floats, and `round(total * r, 2)` is applied per part. The parts need not sum to the total, so cents drift or vanish. | Use integer minor units and largest-remainder allocation. | Property test: `sum(split(total, ratios)) == total` for random inputs. |
| 9 | high | src/billing.py:16 | money-arithmetic | `int(float(amount) * 100)` truncates. For example `"19.99"` can become 1998, and `"0.29"` becomes 28. | Parse with `Decimal` and quantize with a named rounding policy. | Vectors: `"19.99"` gives 1999 and `"0.29"` gives 29. |
| 10 | high | src/documents.py:6 | brazil-payment-rails (CNPJ) | The check accepts any 14 digits, so there is no check-digit validation. It rejects the alphanumeric CNPJ that is valid from July 2026 (today is after that). | Validate the check digits over the alphanumeric format. | A valid alphanumeric CNPJ is accepted. A wrong check digit is rejected. |
| 11 | medium | src/charges.py:5 | money-arithmetic (rates) | The fee rate is a float (`0.035`). The fee computation is not in this module yet, but any use will drift. | Store the rate as a `Decimal` or basis points (350 bp) with one named rounding policy. | Fee on 1,000 cents is exactly 35. |
| 12 | medium | src/settlement.py:6 | brazil-payment-rails (business days) | `datetime.now()` is naive local time, and `+1 day` ignores weekends and Brazilian holidays. The `amount` argument is unused. The date is not testable. | Inject a clock, use UTC, and apply a business-day calendar. | Friday and pre-holiday inputs settle on the next business day. |
| 13 | medium | all of src/ | audit-trail | No mutation records who, what, before/after or why. This covers the charge, the wallet debit and the order status change. | Add append-only audit events for each mutation. | One event per mutation with actor, before/after and idempotency key. |

Counts: 4 critical, 6 high, 3 medium, 0 low.

## Checked and clean
- Nothing was found to be clean. Several areas simply contain no code yet: reconciliation, accounting sync, transaction classification, interest and amortization, and refunds. The first four are listed under "Not checked" for that reason, and refunds are not in the module at all.

## Not checked
- `money_lint.py` and the money-arithmetic vector suites: Bash was disabled in this session, so none of them ran. This was a manual read only.
- Tests: the module has no test files, so no coverage or mutation data exists.
- Everything outside `src/`: infrastructure, database schema and migrations, deployment config, secrets management, dependencies, and the code that calls these functions (for example where `Invoice.total` or `order.amount_cents` come from).
- Reconciliation, accounting sync, transaction classification and interest code: not present in the module, so there was nothing to review.
- Runtime behaviour: nothing was executed.
- This is a correctness and operability review. It is not a security audit or a penetration test, and it gives no legal or tax opinion on LGPD, PCI DSS or fiscal rules.

## Next three changes
1. Charges and boleto (findings 1 and 2): derive the idempotency key from the order id, and stop marking orders paid at boleto issuance. These two remove the double charge and the unpaid fulfilment.
2. Card data and webhooks (findings 3, 4 and 5): drop `cvv` and the PAN from `Card`, verify webhook signatures on the raw body with a configured secret, and stop logging payloads.
3. Money representation (findings 8, 9 and 11): move to integer minor units with largest-remainder allocation, then fix the wallet debit (finding 7) on top of it.
