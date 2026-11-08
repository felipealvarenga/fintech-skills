"""Payout client. Fails sometimes with 5xx and timeouts."""
import requests


def send_payout(payout):
    resp = requests.post("https://bank.example/payouts", json={"amount": payout.amount, "iban": payout.iban}, timeout=5)
    resp.raise_for_status()
    return resp.json()
