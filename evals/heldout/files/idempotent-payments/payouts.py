"""Bank payouts for the ops dashboard."""
import requests


def send_payout(account, amount_minor, currency):
    r = requests.post("https://bank.example/payouts", json={"account": account, "amount": amount_minor, "currency": currency}, timeout=10)
    r.raise_for_status()
    return r.json()["payout_id"]
