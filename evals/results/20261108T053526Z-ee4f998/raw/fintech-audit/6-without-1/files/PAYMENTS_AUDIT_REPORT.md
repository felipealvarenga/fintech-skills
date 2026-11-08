# Payments Module – Code Review Report

**Date:** 2026-11-08
**Scope:** all 8 files in `src/` (billing, boleto, charges, documents, models, settlement, wallet, webhooks)
**Method:** manual static review. No code was executed, no tests exist in the repo, and no runtime, infrastructure, or dependency review was done.
**Result:** 12 findings (6 High, 5 Medium, 1 Low). Several are directly exploitable or cause financial loss.

## Summary

| # | Severity | File | Finding |
|---|----------|------|---------|
| 1 | High | `charges.py:11` | Random idempotency key per call, so retries double-charge |
| 2 | High | `boleto.py:6` | Order marked `paid` when the boleto is issued, not when it is paid |
| 3 | High | `models.py:9` | CVV stored as a field on the card model |
| 4 | High | `webhooks.py:13` | Signature verified against re-serialized JSON, not the raw body |
| 5 | High | `webhooks.py:12` | Full webhook payload written to logs |
| 6 | High | `wallet.py:5` | Wallet debit has no funds check, transaction control, or ledger entry |
| 7 | Medium | `billing.py:5-12` | Money held as `float` |
| 8 | Medium | `billing.py:12` | `round()` on floats; split parts are not guaranteed to sum to the total |
| 9 | Medium | `billing.py:16` | `int(float(x) * 100)` truncates (e.g. `"19.99"` gives 1998) |
| 10 | Medium | `charges.py:5` | Fee rate is a float constant (`0.035`) |
| 11 | Medium | `documents.py:6` | CNPJ validated by format only (no check digits) |
| 12 | Low | `settlement.py:6` | Settlement date uses naive wall-clock time and ignores its input |

## Details

### 1. Random idempotency key (High) – `charges.py:11`
`idempotency_key=str(uuid.uuid4())` is generated on every call. A client retry, timeout, or double submit creates a second PaymentIntent, so the customer can be charged twice. The key must be derived from the order (e.g. order ID plus attempt) and stored.
**Fix:** `idempotency_key=f"charge-{order.id}"`, or a persisted per-attempt key.

### 2. Boleto marked paid on issue (High) – `boleto.py:6`
`order.status = "paid"` runs right after `psp.create_boleto`. A boleto is only a payment slip. Goods or services may be released with no money received, and customers can be left with unpaid boletos on "paid" orders.
**Fix:** set `pending` / `awaiting_payment` here. Move to `paid` only on a confirmed PSP payment/compensation webhook.

### 3. CVV stored (High) – `models.py:9`
`Card` carries `cvv` next to `card_number`. PCI DSS prohibits storing sensitive authentication data after authorization. Storing the full PAN in application models also widens PCI scope.
**Fix:** remove `cvv`. Use PSP tokens (Stripe `payment_method` IDs) instead of raw card data.

### 4. Webhook signature check on re-serialized body (High) – `webhooks.py:11-13`
`json.dumps(request.get_json())` does not reproduce the bytes Stripe signed (key order, whitespace, and unicode escaping can differ). Valid events will fail verification, and the usual workaround is to disable the check. The secret is also hardcoded (`"whsec_x"`). The handler does not catch `SignatureVerificationError`, and a missing header raises `KeyError`.
**Fix:** pass `request.get_data()` (raw bytes) to `construct_event`. Load the secret from configuration. Return 400 on a bad or missing signature.

### 5. Payload logging (High) – `webhooks.py:12`
`log.info("webhook payload %s", payload)` writes the full event, which can include customer and payment data, to logs. This is a LGPD and PCI exposure.
**Fix:** log only the event ID and type.

### 6. Wallet debit (High) – `wallet.py:5`
A bare `UPDATE ... balance = balance - %s`:
- has no `balance >= amount` guard, so balances can go negative and concurrent debits can overspend;
- does not check the affected row count, so an unknown user is silently ignored;
- has no visible commit or transaction boundary;
- writes no ledger or audit entry;
- has no idempotency, so a retry debits twice.

**Fix:** `... SET balance = balance - %s WHERE user_id = %s AND balance >= %s`, check `rowcount`, and insert a ledger row in the same transaction with a unique operation ID.

### 7–9. Float money in billing (Medium) – `billing.py`
- `Invoice.total` and the split functions use `float`.
- `split_invoice` rounds each share independently, so the sum of the parts can differ from the total by a cent or more. Nothing allocates the remainder.
- `to_cents("19.99")` returns 1998 because `19.99 * 100 = 1998.9999…` and `int()` truncates. This silently under-charges.

**Fix:** use `Decimal` or integer cents end to end. Parse with `Decimal(amount)`. Split with a largest-remainder allocation so the parts sum exactly to the total.

### 10. Float fee rate (Medium) – `charges.py:5`
`PLATFORM_FEE_RATE = 0.035` is currently unused, but it will introduce float error as soon as it is applied. Use `Decimal("0.035")` or basis points (350) with an explicit rounding mode.

### 11. CNPJ validation (Medium) – `documents.py:6`
The check is `\d{14}` only:
- it accepts any 14 digits, including invalid or repeated-digit values, because the check digits are not verified;
- it rejects formatted input (`12.345.678/0001-95`) with no normalization step;
- Brazil's alphanumeric CNPJ (Receita Federal, effective July 2026) will be rejected. Please confirm the current rules with your compliance team.

### 12. Settlement date (Low) – `settlement.py:6`
- `datetime.now()` is naive and server-local. Use an explicit timezone (e.g. `America/Sao_Paulo`).
- It always returns +1 calendar day. Business days and bank holidays are not considered.
- The `amount` parameter is unused.

## Not assessed
- No tests exist, so there is no coverage evidence.
- Authentication, authorization, and rate limiting on the endpoints are not in this repo.
- Dependency versions, secrets management, deployment, and database schema were not available.
- Findings are from reading the code and have not been reproduced at runtime.

## Suggested remediation order
1. Fix findings 1, 2, 4, 6 (money loss or incorrect payment state).
2. Fix findings 3 and 5 (PCI and LGPD exposure).
3. Fix findings 7–10 (switch to Decimal or integer money).
4. Fix findings 11 and 12.
5. Add tests for each fix.
