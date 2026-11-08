"""Post categorized transactions."""
THRESHOLD = 0.5


def post_if_confident(ledger, tx, category, confidence):
    if confidence >= THRESHOLD:
        ledger.post(tx["id"], category)
