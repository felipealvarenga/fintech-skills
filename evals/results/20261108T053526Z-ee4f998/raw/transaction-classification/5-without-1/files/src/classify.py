"""Categorize bank transactions with an LLM and post them."""
import json
from datetime import date

TRANSFER_CATEGORY = "Transfer"
TRANSFER_KEYWORDS = ("TRANSFER TO", "TRANSFER FROM")
MAX_TRANSFER_DAYS = 3


def _amount(t):
    return int(t.get("amount_minor", t.get("amount")))


def is_transfer(transaction, all_transactions=()):
    """True if the transaction is one leg of an internal transfer.

    A transfer is a pair of rows on different accounts with opposite amounts
    within a few days of each other. If the description also looks like a
    transfer, that is enough on its own when the counterpart is not in the
    batch (e.g. statement cut-off between the two legs).
    """
    amount = _amount(transaction)
    when = date.fromisoformat(transaction["date"])
    for other in all_transactions:
        if other["id"] == transaction["id"] or other["account"] == transaction["account"]:
            continue
        if _amount(other) != -amount:
            continue
        if abs((date.fromisoformat(other["date"]) - when).days) <= MAX_TRANSFER_DAYS:
            return True
    desc = transaction["description"].upper()
    return any(k in desc for k in TRANSFER_KEYWORDS)


def categorize_and_post(llm, ledger, transaction, chart, all_transactions=()):
    if is_transfer(transaction, all_transactions):
        ledger.post(transaction["id"], TRANSFER_CATEGORY)
        return
    prompt = f"Categorize this transaction into one of {chart}: {transaction['description']} {_amount(transaction)}"
    category = llm.complete(prompt).strip()
    ledger.post(transaction["id"], category)
