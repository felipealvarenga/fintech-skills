import csv
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from export import export_customers, mask_document  # noqa: E402


class FakeDB:
    def query(self, sql):
        assert "phone" not in sql and "cpf" in sql
        return [NS(name="Ana", email="ana@example.com", cpf="529.982.247-25"),
                NS(name="=cmd()", email="b@example.com", cpf=None)]


def test_export_masks_document_and_drops_phone(tmp_path):
    p = tmp_path / "out.csv"
    export_customers(FakeDB(), str(p))
    text = p.read_text()
    assert "52998224725" not in text and "529.982.247-25" not in text
    rows = list(csv.reader(text.splitlines()))
    assert rows[0] == ["name", "email", "document_masked"]
    assert rows[1] == ["Ana", "ana@example.com", "*******4725"]
    assert rows[2][0].startswith("'=")


def test_mask_document():
    assert mask_document("52998224725") == "*******4725"
    assert mask_document("") == ""
