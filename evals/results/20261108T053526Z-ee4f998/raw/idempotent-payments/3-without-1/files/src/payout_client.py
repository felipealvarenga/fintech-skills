"""Payout client. Fails sometimes with 5xx and timeouts."""
import logging
import random
import time
import uuid

import requests

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
BASE_DELAY = 0.5  # seconds, doubled each attempt with jitter


def send_payout(payout):
    # One idempotency key for all attempts, so a retry after a timeout
    # (where the bank may have processed the first request) can't pay twice.
    key = getattr(payout, "id", None) or str(uuid.uuid4())
    headers = {"Idempotency-Key": str(key)}
    body = {"amount": payout.amount, "iban": payout.iban}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(
                "https://bank.example/payouts", json=body, headers=headers, timeout=5
            )
            if resp.status_code >= 500:
                resp.raise_for_status()
            resp.raise_for_status()  # 4xx: raised immediately, not retried
            return resp.json()
        except (requests.Timeout, requests.ConnectionError) as exc:
            err = exc
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code < 500:
                raise
            err = exc

        if attempt == MAX_ATTEMPTS:
            raise err
        delay = BASE_DELAY * 2 ** (attempt - 1) * random.uniform(0.5, 1.5)
        logger.warning("send_payout attempt %d failed (%s); retrying in %.1fs", attempt, err, delay)
        time.sleep(delay)
