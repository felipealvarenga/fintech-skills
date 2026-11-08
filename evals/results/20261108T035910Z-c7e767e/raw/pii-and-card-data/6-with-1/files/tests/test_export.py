import csv
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from export import export_customers, mask_document  # noqa: E402


class FakeDB:
    def query(self, sql):
        assert "name" not in sql and "phone" not in sql
        return [SimpleNamespace(email="a@example.com", cpf="529.982.247-25")]


def test_mask_document():
    assert mask_document("529.982.247-25") == "*******4725"
    assert mask_document("52998224725") == "*******4725"


def test_export_has_no_full_cpf(tmp_path):
    p = tmp_path / "out.csv"
    export_customers(FakeDB(), str(p))
    text = p.read_text()
    assert "52998224725" not in text and "529.982.247-25" not in text
    rows = list(csv.reader(text.splitlines()))
    assert rows == [["email", "document_masked"], ["a@example.com", "*******4725"]]
