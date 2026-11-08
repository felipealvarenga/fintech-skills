"""Categorize bank transactions with an LLM and post them."""
import json


def categorize_and_post(llm, ledger, transaction, chart):
    prompt = f"Categorize this transaction into one of {chart}: {transaction['description']} {transaction['amount']}"
    category = llm.complete(prompt).strip()
    ledger.post(transaction["id"], category)
