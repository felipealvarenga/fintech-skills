"""Categorize bank transactions with an LLM and post them."""
import json

# Customer rules: case-insensitive merchant substring -> category.
# A matching rule takes precedence over the LLM.
DEFAULT_RULES = {
    "uber": "Travel",
}


def apply_rules(description, rules):
    """Return the category of the first rule whose keyword appears in description, else None."""
    text = description.lower()
    for keyword, category in rules.items():
        if keyword.lower() in text:
            return category
    return None


def categorize_and_post(llm, ledger, transaction, chart, rules=None):
    rules = DEFAULT_RULES if rules is None else rules
    category = apply_rules(transaction["description"], rules)
    if category is None:
        prompt = f"Categorize this transaction into one of {chart}: {transaction['description']} {transaction['amount']}"
        category = llm.complete(prompt).strip()
    ledger.post(transaction["id"], category)
