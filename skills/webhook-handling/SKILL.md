---
name: webhook-handling
description: >-
  Use when code receives callbacks from a payment processor, bank, PSP or any provider that
  reports money events. Covers signature verification on the raw body with timestamp tolerance,
  treating the payload as a notification and confirming state by API before acting, dedupe by
  event id, out-of-order delivery, store-then-acknowledge with asynchronous processing, correct
  status codes for retry, secret rotation, replay tooling and lag monitoring. Triggers on a new
  webhook endpoint, a missed or duplicated event, a provider retry storm, a status that never
  updates. Not for outbound webhooks you send to customers, though most rules transfer.
license: MIT
metadata:
  author: Felipe Alvarenga
  version: 0.1.0
---

# Webhook handling

A webhook is a hint from someone else's system, delivered at least once, in any order, by
anyone who can reach the URL. Code that treats it as a trusted, ordered, exactly-once command
will mark unpaid orders paid and pay refunds twice. Code that follows the rules below is boring,
which is the goal.

## When to use

- A new endpoint that receives events from a processor, PSP, bank, KYC vendor or similar.
- A bug where an order stays pending, flips to paid without payment, or gets two refunds.
- A provider dashboard shows failed deliveries or retries.
- A provider rotates or leaks a webhook secret.

## Rules

1. **Verify the signature on the raw body, before parsing.** Use the provider SDK's verifier
   or a constant-time HMAC comparison over the exact bytes received. A framework that parses
   JSON before your handler breaks verification; read the raw body. Reject a timestamp outside
   the tolerance window (Stripe's default is 300 seconds) to limit replays.
2. **The payload is a notification, not the truth.** For any decision that moves money or
   changes a customer-visible status, fetch the object from the provider API by id and act on
   that state. The payload tells you something changed; the API tells you what it is now.
3. **Dedupe by event id, in the database.** Insert the event id into a table with a unique
   index before processing. A duplicate insert means the event was seen: acknowledge and stop.
4. **Expect events out of order.** `captured` may arrive before `authorized`. Design handlers
   around the object's current state (rule 2), not the sequence of events. A handler that
   receives an older state than the one already recorded does nothing.
5. **Store, acknowledge, then process.** Persist the raw event and return 2xx within a few
   seconds. Process from a queue or a worker. Slow handlers cause provider timeouts, which cause
   retries, which cause duplicates.
6. **Status codes drive provider retries.** Return 2xx when the event is stored (even if you
   do not handle that type). Return 4xx for a bad signature or malformed body (no retry wanted).
   Return 5xx only when storage itself failed and a retry can help.
7. **Secrets are per endpoint and rotate without downtime.** Keep two active secrets during
   rotation; verify against both; remove the old one after the provider confirms. Secrets live
   in the secret manager, never in the repo or in logs.
8. **Replay is a feature.** A command or admin action re-processes a stored event by id, in
   staging and in production, with an audit record of who replayed what and why. This is how
   you recover from a handler bug without asking the provider to resend.
9. **One endpoint per provider and per environment.** Test-mode and live-mode events never
   share a URL or a secret. The handler refuses an event whose mode does not match the
   environment.
10. **Monitor lag and failures.** Track provider timestamp to processed timestamp per event
    type, processing failures per type, and unknown event types. Alert on lag above the SLA and
    on any failure rate above a small threshold.

## How to apply

1. Read the provider's webhook documentation for: signature scheme, timestamp header,
   retry schedule, event ordering guarantees (usually none), and test tooling.
2. Implement verification as the first line of the handler, on the raw body. Add the
   timestamp check.
3. Create the `webhook_events` table: provider, event id (unique), type, received at, raw
   payload, status, processed at, error. Insert before anything else.
4. Return 2xx right after the insert. Hand the event id to a worker.
5. In the worker, fetch the object by API, compare with the recorded state, apply the change
   through the same state machine the rest of the system uses (see `idempotent-payments`).
6. Write the tests in the **Tests** section. Use the provider's CLI or fixtures to produce
   signed payloads.
7. Add the replay command and the lag dashboard before shipping.

## Tests the change must include

- Invalid signature: 400, nothing stored, nothing processed.
- Valid signature with a stale timestamp: rejected.
- Valid event: stored, 2xx, processed once.
- Same event id delivered twice: 2xx both times, processed once.
- `captured` before `authorized`: final state is captured; no error, no regression to
  authorized when the older event arrives.
- Payload says paid, API says still pending: nothing changes.
- Handler raises during processing: event marked failed and retryable; the provider got 2xx;
  the replay command processes it after the fix.
- Live-mode event on the test endpoint: refused.
- Reference vectors: `skills/webhook-handling/evals/vectors/test_webhooks.py` with
  `WEBHOOK_SOLUTION` pointing at your module (signature, tolerance, rotation, dedupe, order).

## Review checklist

- Is verification on the raw bytes and before any parsing?
- Where is the unique index on the event id, and is the insert before processing?
- Does any handler change a money state from the payload alone?
- What does the handler do when the event's state is older than the recorded state?
- Which status code is returned for each failure class?
- How does a secret rotate, and where are the two secrets read from?
- How do we replay event `evt_123` in production, and who can?

## Anti-patterns and fixes

| Anti-pattern | What goes wrong | Fix |
|---|---|---|
| Verifying after `JSON.parse` | Signature never matches, so verification gets disabled | Raw body middleware |
| Marking the order paid from the payload | Spoofed or stale payload pays the order | Fetch by API, apply by state machine |
| Processing inside the request | Timeouts, provider retries, duplicates | Store, acknowledge, process from a queue |
| Returning 500 for an unhandled event type | Provider retries forever | 2xx for stored events of any type |
| Secret in an environment variable committed to the repo | Leak, no rotation path | Secret manager, two active secrets |
| No way to replay | Handler bug means lost events | Replay command with audit |

## References

- Stripe webhook documentation: signature verification, timestamp tolerance, retry schedule, event ordering.
- Standard Webhooks specification for a provider-neutral signature and header scheme.
