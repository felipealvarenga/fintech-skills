# Payments Module – Code Review Report

**Date:** 2026-11-08
**Scope:** `src/` (9 files: billing, boleto, charges, documents, models, settlement, wallet, webhooks, plus README)
**Method:** Manual static review of source. No code was executed, no tests exist in the repo, and no runtime, infrastructure, or dependency review was performed.
**Note:** The README describes this as a fixture with planted defects and no real data. Findings below are on the code as written.

## 1. Summary

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | Critical | `models.py` | CVV stored alongside full card number |
| 2 | Critical | `charges.py` | Random idempotency key per call: retries can double-charge |
| 3 | Critical | `boleto.py` | Order marked `paid` when boleto is issued, not when paid |
| 4 | High | `webhooks.py` | Signature verified against re-serialized JSON, not raw body |
| 5 | High | `webhooks.py` | Full webhook payload logged (sensitive data in logs) |
| 6 | High | `wallet.py` | Balance debit has no funds check, transaction control, or ledger entry |
| 7 | High | `billing.py` | Money handled as binary floats; truncating cents conversion |
| 8 | Medium | `billing.py` | Invoice split can fail to sum to total |
| 9 | Medium | `documents.py` | CNPJ validation checks only "14 digits" |
| 10 | Medium | `settlement.py` | Naive wall-clock time; ignores amount and business days |
| 11 | Medium | `charges.py` | Platform fee rate is a float |
| 12 | Medium | `webhooks.py` | Hardcoded secret, no error handling, no event de-duplication |

## 2. Findings

### 1. CVV stored in model (Critical) – `models.py:9`
`Card` holds `card_number`, `cvv` and `expiry` together. PCI DSS forbids retaining card verification codes after authorization, and full PANs should not be held unless required and protected.
**Recommendation:** Remove `cvv` from the model. Use PSP tokenization (Stripe Elements or payment methods) so raw card data never reaches this service.

### 2. Non-deterministic idempotency key (Critical) – `charges.py:11`
`idempotency_key=str(uuid.uuid4())` generates a new key on every call, so a client or network retry creates a second PaymentIntent and the customer is charged twice.
**Recommendation:** Derive the key from a stable identifier, such as the order ID plus attempt, and persist it.

### 3. Boleto marked paid at issuance (Critical) – `boleto.py:6`
`order.status = "paid"` is set right after the boleto is created. A boleto is only a payment instrument and is settled later, if at all. Goods or services may be released for unpaid orders.
**Recommendation:** Set a status such as `awaiting_payment`. Move to `paid` only on a confirmed compensation or settlement notification from the PSP.

### 4. Webhook signature verification on re-serialized body (High) – `webhooks.py:11,13`
The code parses the JSON and then verifies `json.dumps(payload)`. Stripe signs the exact raw bytes, so re-serialization can change whitespace or key order. This causes valid events to fail verification, and it weakens the integrity guarantee.
**Recommendation:** Use `request.get_data()` (raw bytes) for `construct_event`.

### 5. Payload logged in full (High) – `webhooks.py:12`
`log.info("webhook payload %s", payload)` writes complete event bodies, which can include customer and payment data, to application logs. This is also done before the signature is verified, so unauthenticated input is logged.
**Recommendation:** Log only event ID and type, and only after verification.

### 6. Wallet debit is unsafe (High) – `wallet.py:5`
The `UPDATE ... balance = balance - %s` statement:
- has no check for sufficient balance, so balances can go negative;
- has no validation of `amount` (a negative amount credits the wallet);
- does not check whether the user exists (zero rows affected passes silently);
- shows no transaction boundary or commit, and writes no ledger or audit record.

**Recommendation:** Use a conditional update (`WHERE balance >= %s`) and check the affected row count. Insert an immutable ledger entry in the same transaction and validate `amount > 0`.

### 7. Floating-point money (High) – `billing.py:5-16`
`Invoice.total` and the split functions use `float`. `to_cents` uses `int(float(amount) * 100)`, which truncates. For example, `"19.99"` evaluates to `1998.9999999999998`, which becomes `1998` cents, so the amount is one cent short.
**Recommendation:** Use `Decimal` or integer cents throughout. Parse strings with `Decimal` and quantize explicitly.

### 8. Split rounding (Medium) – `billing.py:12`
Each share is rounded independently with float `round`, so the parts may not sum to the total, and cents are created or lost. There is no remainder allocation.
**Recommendation:** Work in integer cents, floor each share, and distribute the remainder deterministically. Assert that the sum equals the total.

### 9. Weak CNPJ validation (Medium) – `documents.py:6`
The regex `\d{14}` does not verify check digits, accepts invalid or all-same-digit numbers, and rejects the common formatted form (`00.000.000/0000-00`). Brazil's alphanumeric CNPJ also began being issued in July 2026, so a digits-only rule will reject valid new registrations.
**Recommendation:** Normalize the input, implement the check-digit algorithm (including the alphanumeric format), and reject repeated-digit values.

### 10. Settlement date (Medium) – `settlement.py:6`
Uses naive `datetime.now()` (server-local time, no timezone). The `amount` argument is unused, and the date is always "+1 day" with no business-day or holiday calendar, so weekend and holiday settlement dates will be wrong.
**Recommendation:** Use timezone-aware time (for example `America/Sao_Paulo`), inject the clock for testability, and apply the actual settlement rules and calendar.

### 11. Fee rate as float (Medium) – `charges.py:5`
`PLATFORM_FEE_RATE = 0.035` is a binary float and invites float arithmetic on money. It is currently unused in this file, so its consumers should be checked.
**Recommendation:** Use `Decimal("0.035")` or basis points (350) with integer math.

### 12. Webhook hardening (Medium) – `webhooks.py:13`
- The secret `"whsec_x"` is hardcoded and should come from configuration or a secrets manager.
- `SignatureVerificationError` and `ValueError` are not handled, so bad requests produce a 500 instead of a 400.
- Events are not de-duplicated by `event.id`, so redelivery causes repeated processing.

## 3. Positive observations
- The module is small and each file has a clear single purpose.
- Charge amounts are passed to the PSP as integer cents (`amount_cents`), and the currency is explicit.
- The wallet query is parameterized, so it is not vulnerable to SQL injection.

## 4. Limitations
- Static review only. Findings were not confirmed by running the code.
- There are no tests in the repo, so test coverage is zero as far as can be seen.
- Callers of these functions, the database schema, deployment, access control, and dependency versions were not available and were not reviewed.
- Issues #1–#3 should be fixed before this code handles real transactions.
