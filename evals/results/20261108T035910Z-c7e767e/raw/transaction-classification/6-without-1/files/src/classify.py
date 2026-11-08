"""Categorize bank transactions with an LLM and post them."""
import json


# Customer rules: (case-insensitive substring of description, category).
# Checked in order; the first match wins and the LLM is skipped.
CUSTOMER_RULES = [
    ("uber", "Travel"),
]


def apply_rules(description, rules=CUSTOMER_RULES):
    """Return the category of the first matching rule, or None."""
    desc = description.lower()
    for keyword, category in rules:
        if keyword.lower() in desc:
            return category
    return None


def categorize_and_post(llm, ledger, transaction, chart, rules=CUSTOMER_RULES):
    category = apply_rules(transaction["description"], rules)
    if category is None:
        prompt = f"Categorize this transaction into one of {chart}: {transaction['description']} {transaction['amount']}"
        category = llm.complete(prompt).strip()
    ledger.post(transaction["id"], category)
