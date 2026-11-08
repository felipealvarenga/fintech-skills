import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from customer_model import Customer, PaymentMethod, forbidden_fields

SAMPLE = PaymentMethod("c1", "visa", "4242", "tok_abc123", "processor_a", 12, 2030)


def test_schema_lint_no_forbidden_columns():
    assert forbidden_fields(PaymentMethod) == set()
    assert forbidden_fields(Customer) == set()


def test_public_representation_excludes_token_and_pan():
    public = SAMPLE.to_public()
    assert "token" not in public
    assert not (set(public) & {"pan", "card_number", "cvv", "cvc", "security_code"})
    assert public["last4"] == "4242"


def test_token_is_tied_to_a_processor():
    assert SAMPLE.processor == "processor_a"
