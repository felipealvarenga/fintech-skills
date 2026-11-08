import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from payouts import Payout, apply_platform_fee, platform_fee, fee_batch


def test_fee_exact():
    assert platform_fee(10000) == 350


def test_fee_half_even_rounding():
    # 3.5% of 10 = 0.35 -> 0 ; of 50 = 1.75 -> 2 ; of 100 = 3.5 -> 4 (half-even)
    assert platform_fee(10) == 0
    assert platform_fee(50) == 2
    assert platform_fee(100) == 4
    assert platform_fee(300) == 10  # 10.5 -> 10 (half-even)


def test_fee_is_stored_and_amount_unchanged():
    p = apply_platform_fee(Payout("a", 12345))
    assert p.fee_minor == 432  # 432.075 -> 432
    assert p.amount_minor == 12345
    assert isinstance(p.fee_minor, int)


def test_fee_batch():
    ps = [apply_platform_fee(Payout(str(i), 1000)) for i in range(3)]
    assert fee_batch(ps) == 105
