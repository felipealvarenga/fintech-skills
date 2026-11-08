"""Synthetic data generators for staging. Never reads production."""
import random
import re

FIRST = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabi", "Heitor", "Iris", "João"]
LAST = ["Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Ribeiro", "Alves", "Rocha"]


def cpf_digit(digits):
    s = sum(int(d) * w for d, w in zip(digits, range(len(digits) + 1, 1, -1)))
    r = (s * 10) % 11
    return str(0 if r == 10 else r)


def gen_cpf(rng):
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if len(set(base)) > 1:
            break
    d1 = cpf_digit(base)
    d2 = cpf_digit(base + d1)
    return base + d1 + d2


def valid_cpf(cpf):
    return bool(re.fullmatch(r"\d{11}", cpf)) and len(set(cpf)) > 1 and \
        cpf[9] == cpf_digit(cpf[:9]) and cpf[10] == cpf_digit(cpf[:10])


def luhn_ok(num):
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def gen_name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def gen_email(i):
    # example.test is a reserved TLD: can never reach a real mailbox
    return f"user{i:05d}@example.test"


def gen_card_token(rng):
    """Only token, brand, last4, expiry. No PAN, no CVV."""
    return {
        "token": "tok_test_" + "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=16)),
        "brand": rng.choice(["visa", "mastercard", "elo"]),
        "last4": rng.choice(["4242", "0004", "1111", "5100"]),
        "exp": f"{rng.randint(1, 12):02d}/{rng.randint(27, 31)}",
    }


def gen_customers(n, seed=1):
    rng = random.Random(seed)
    return [
        {"id": i, "name": gen_name(rng), "email": gen_email(i), "cpf": gen_cpf(rng),
         **{f"card_{k}": v for k, v in gen_card_token(rng).items()}}
        for i in range(1, n + 1)
    ]
