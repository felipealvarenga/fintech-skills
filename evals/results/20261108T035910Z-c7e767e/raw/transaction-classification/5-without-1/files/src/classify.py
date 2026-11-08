"""Categorize bank transactions with an LLM and post them."""
import json
from datetime import date

TRANSFER_CATEGORY = "Transfer"
MAX_TRANSFER_GAP_DAYS = 3


def find_transfer_ids(transactions):
    """Return ids of transactions that are two legs of an internal transfer.

    A pair is two transactions on different accounts with opposite amounts,
    dated within MAX_TRANSFER_GAP_DAYS of each other. Each transaction is
    used in at most one pair.
    """
    parsed = [
        (t["id"], t["account"], date.fromisoformat(t["date"]), int(t["amount_minor"]))
        for t in transactions
    ]
    matched = set()
    for id_a, acct_a, date_a, amt_a in parsed:
        if id_a in matched or amt_a >= 0:
            continue
        for id_b, acct_b, date_b, amt_b in parsed:
            if (
                id_b not in matched
                and acct_b != acct_a
                and amt_b == -amt_a
                and abs((date_b - date_a).days) <= MAX_TRANSFER_GAP_DAYS
            ):
                matched.update((id_a, id_b))
                break
    return matched


def categorize_and_post(llm, ledger, transaction, chart, transfer_ids=frozenset()):
    """Post a transaction. Pass transfer_ids from find_transfer_ids(batch)."""
    if transaction["id"] in transfer_ids:
        ledger.post(transaction["id"], TRANSFER_CATEGORY)
        return
    prompt = f"Categorize this transaction into one of {chart}: {transaction['description']} {transaction['amount_minor']}"
    category = llm.complete(prompt).strip()
    ledger.post(transaction["id"], category)
