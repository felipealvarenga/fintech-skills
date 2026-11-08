"""Payout client. Fails sometimes with 5xx and timeouts."""
import logging
import random
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    max_total_seconds: float = 30.0
    base_delay: float = 0.5
    max_delay: float = 8.0


DEFAULT_RETRY_POLICY = RetryPolicy()


def _retryable(exc):
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    return False


def _delay(policy, attempt, exc):
    resp = getattr(exc, "response", None)
    if resp is not None and resp.status_code == 429:
        try:
            return min(float(resp.headers.get("Retry-After", "")), policy.max_delay)
        except ValueError:
            pass
    return random.uniform(0, min(policy.max_delay, policy.base_delay * 2 ** (attempt - 1)))


def send_payout(payout, policy=DEFAULT_RETRY_POLICY):
    # The key is derived from the payout id, never random per attempt, so a retry
    # after a timeout (unknown outcome) cannot create a second payout at the bank.
    headers = {"Idempotency-Key": f"payout:{payout.id}"}
    body = {"amount": payout.amount, "iban": payout.iban}
    start = time.monotonic()

    for attempt in range(1, policy.max_attempts + 1):
        try:
            resp = requests.post("https://bank.example/payouts", json=body, headers=headers, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            delay = _delay(policy, attempt, exc) if _retryable(exc) else None
            out_of_budget = (
                delay is None
                or attempt == policy.max_attempts
                or time.monotonic() - start + delay > policy.max_total_seconds
            )
            log.warning("payout %s attempt %d failed: %r (retry=%s)", payout.id, attempt, exc, not out_of_budget)
            if out_of_budget:
                raise
            time.sleep(delay)
