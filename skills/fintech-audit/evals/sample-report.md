<!-- Sample output. Produced by claude-sonnet-5-5 with the fintech-audit skill on the planted fixture (evals/files/audit-fixture) on 2026-11-08: 7 turns, USD 0.21, no code changed. Two false leads from scanning the lint's own source were dropped by the agent; the lint now skips agent config folders. Kept verbatim. -->

# Money audit: proj (not a git repo, no SHA)

Lint: 17 leads. 2 dropped (money_lint.py:20, :42, the lint's own regex source). 15 confirmed by reading code, grouped into 12 findings.

| # | Sev | Where | Rule | What happens | Fix | Test to add |
|---|---|---|---|---|---|---|
| 1 | critical | src/models.py:8-9 | pii-and-card-data 1 | Model stores full card number and CVV | Store processor token, brand, last4 | Model has no PAN/CVV field |
| 2 | critical | src/charges.py:11 | idempotent-payments 4 | uuid4 key per attempt; timeout + retry double charges | Key derived from order id | Two calls for one order send the same key |
| 3 | critical | src/boleto.py:6 | brazil-payment-rails 6 | Order marked paid on boleto issue | Stay pending until PSP confirms | Status is pending after generate_boleto |
| 4 | critical | src/webhooks.py:11-13 | webhook-handling 1 | Signature checked on json.dumps(parsed), not raw body; secret "whsec_x" hardcoded | Use request.get_data(); secret from config | Raw body with valid signature passes; re-serialized fails |
| 5 | high | src/webhooks.py:12 | pii-and-card-data 3 | Full payload logged | Log event id and type only | Log has no payload fields |
| 6 | high | src/wallet.py:5 | double-entry-ledger 1, 4 | balance = balance - x: no ledger, no overdraft guard, no idempotency | Immutable entries, derived balance, operation key | Overdraft rejected; same op id debits once |
| 7 | high | src/billing.py:8,11-12 | money-arithmetic 1, 4 | Float amounts, round(x*r, 2) split; parts may not sum to total | Integer minor units, largest-remainder split | Parts sum to total, e.g. split(100, [1/3]*3) |
| 8 | high | src/billing.py:16 | money-arithmetic 1, 2 | int(float("19.99")*100) = 1998; hardcoded 100 | Decimal parse, ISO 4217 exponent | to_cents("19.99") == 1999; JPY exponent 0 |
| 9 | high | src/charges.py:5 | money-arithmetic 6 | Fee rate is float 0.035 | Decimal("0.035"), named rounding | Fee on 1999 cents matches expected integer |
| 10 | high | src/documents.py:6 | brazil-payment-rails 12 | \d{14} rejects alphanumeric CNPJs (from July 2026); no check digits | Validate format and check digits | Valid alphanumeric passes; bad digit fails |
| 11 | medium | src/settlement.py:6 | money-tests 7 | Naive datetime.now(), untestable, ignores business days | Inject clock, aware timezone | Fixed clock gives fixed date |
| 12 | medium | src/webhooks.py | webhook-handling | No event-id dedupe | Store processed event ids | Same event id twice has one effect |

#6 and #12 came from reading the code; the lint did not flag them.

## Checked and clean
None. Every file has at least one finding.

## Not checked
- Vector suites: no money module in the repo passes them.
- Reconciliation, accounting-sync, audit-trail, interest-and-amortization, transaction-classification: no code exists.
- Tests, schema, migrations, runtime and deploy config: not in the repo.

## Next three changes
1. Remove cvv/card_number (#1), fix idempotency key (#2), stop marking boletos paid on issue (#3).
2. Verify webhook signature on raw body with configured secret, stop logging payloads, add event dedupe (#4, #5, #12).
3. Move to integer minor units and Decimal rates (#7-9), then build the ledger wallet (#6).
