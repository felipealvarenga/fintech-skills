"""Payout client with bounded, selective retries.

A timeout on a payout is an unknown outcome, so every attempt re-sends the
SAME idempotency key (derived from payout.id). The bank must honor it for the
retries to be safe.
"""
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


PAYOUT_RETRY_POLICY = RetryPolicy()


def _retryable_status(status):
    return status == 429 or 500 <= status < 600


def _delay(policy, attempt, resp=None):
    if resp is not None and resp.status_code == 429:
        try:
            return min(float(resp.headers["Retry-After"]), policy.max_delay)
        except (KeyError, ValueError):
            pass
    backoff = min(policy.max_delay, policy.base_delay * 2 ** (attempt - 1))
    return random.uniform(0, backoff)  # full jitter


def send_payout(payout, policy=PAYOUT_RETRY_POLICY, _sleep=time.sleep):
    key = f"payout-{payout.id}"  # deterministic: never a fresh value per attempt
    body = {"amount": payout.amount, "iban": payout.iban}
    start = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        resp = None
        try:
            resp = requests.post(
                "https://bank.example/payouts",
                json=body,
                headers={"Idempotency-Key": key},
                timeout=5,
            )
            if not _retryable_status(resp.status_code):
                resp.raise_for_status()  # 4xx: raised, never retried
                log.info("payout key=%s attempt=%d ok", key, attempt)
                return resp.json()
            err = requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
        except (requests.ConnectionError, requests.Timeout) as e:
            err = e

        delay = _delay(policy, attempt, resp)
        elapsed = time.monotonic() - start
        log.warning("payout key=%s attempt=%d failed: %s", key, attempt, err)
        if attempt >= policy.max_attempts or elapsed + delay > policy.max_total_seconds:
            # Outcome may be unknown: caller must leave the payout pending
            # and reconcile with the bank, not mark it failed or re-key it.
            raise err
        _sleep(delay)
