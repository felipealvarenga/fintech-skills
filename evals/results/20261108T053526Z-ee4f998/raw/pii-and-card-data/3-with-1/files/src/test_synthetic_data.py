import random
import re

from synthetic_data import gen_cpf, valid_cpf, luhn_ok, gen_customers, gen_card_token


def test_cpf_valid_check_digits():
    rng = random.Random(0)
    assert all(valid_cpf(gen_cpf(rng)) for _ in range(500))


def test_cpf_validator_rejects_bad():
    assert not valid_cpf("11111111111")
    assert not valid_cpf("12345678900")


def test_luhn_reference():
    assert luhn_ok("4242424242424242")
    assert not luhn_ok("4242424242424243")


def test_no_pan_or_cvv_fields():
    for c in gen_customers(50):
        assert not any(k in c for k in ("pan", "card_number", "cvv", "cvc", "security_code"))
        assert not re.search(r"\b\d{13,19}\b", " ".join(map(str, c.values())))
        assert len(c["card_last4"]) == 4


def test_emails_are_non_routable():
    assert all(c["email"].endswith("@example.test") for c in gen_customers(50))


def test_deterministic():
    assert gen_customers(5, seed=3) == gen_customers(5, seed=3)
    assert gen_card_token(random.Random(1))["token"].startswith("tok_test_")
