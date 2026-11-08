import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from billing_float import invoice_total  # noqa: E402


def test_no_drift():
    assert invoice_total([0.1, 0.2, 0.3]) == 0.6


def test_empty_and_negative():
    assert invoice_total([]) == 0.0
    assert invoice_total([10.0, -0.01]) == 9.99


def test_many_small_lines():
    assert invoice_total([0.01] * 100) == 1.0


def test_sub_centavo_refused():
    with pytest.raises(ValueError):
        invoice_total([0.001])


def test_nan_refused():
    with pytest.raises(ValueError):
        invoice_total([float("nan")])
