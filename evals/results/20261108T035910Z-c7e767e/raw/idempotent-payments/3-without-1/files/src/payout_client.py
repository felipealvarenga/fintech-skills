"""Payout client. Fails sometimes with 5xx and timeouts."""
import time
import uuid

import requests

MAX_ATTEMPTS = 4
BACKOFF_BASE = 0.5  # seconds; doubles each retry


def send_payout(payout):
    # One key for all attempts so the bank can deduplicate if a request
    # succeeded but its response was lost.
    key = str(getattr(payout, "id", None) or uuid.uuid4())
    body = {"amount": payout.amount, "iban": payout.iban}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(
                "https://bank.example/payouts",
                json=body,
                headers={"Idempotency-Key": key},
                timeout=5,
            )
            if resp.status_code < 500:
                resp.raise_for_status()  # 4xx: not retryable, raise immediately
                return resp.json()
            err = requests.HTTPError(f"{resp.status_code} from bank", response=resp)
        except (requests.Timeout, requests.ConnectionError) as e:
            err = e

        if attempt == MAX_ATTEMPTS:
            raise err
        time.sleep(BACKOFF_BASE * 2 ** (attempt - 1))
