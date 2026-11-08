import random
from ledger import post, trial_balance


def test_random_entries_balance():
    for _ in range(5000):
        entries = [random.randint(-10_000, 10_000) for _ in range(20)]
        entries.append(-sum(entries))
        post(entries)
        assert trial_balance() == 0
