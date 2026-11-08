import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ledger import LedgerError, validate_postings  # noqa: E402


def test_balanced_posts():
    validate_postings([(1, "debit", 100, "BRL"), (2, "credit", 100, "BRL")])


def test_unbalanced_raises():
    with pytest.raises(LedgerError):
        validate_postings([(1, "debit", 100, "BRL"), (2, "credit", 90, "BRL")])


def test_single_posting_raises():
    with pytest.raises(LedgerError):
        validate_postings([(1, "debit", 100, "BRL")])


def test_balanced_in_total_not_per_currency_raises():
    with pytest.raises(LedgerError):
        validate_postings([(1, "debit", 100, "BRL"), (2, "credit", 100, "USD")])


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_raises(amount):
    with pytest.raises(LedgerError):
        validate_postings([(1, "debit", amount, "BRL"), (2, "credit", amount, "BRL")])
