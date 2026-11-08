from datetime import date, datetime, timezone

import pytest

from recon import adapters, dashboard, store
from recon.models import Config
from recon.reconcile import reconcile


def test_to_minor_handles_exponents_and_rejects_excess_precision():
    assert adapters.to_minor("12.34", "USD") == 1234
    assert adapters.to_minor("500", "JPY") == 500
    with pytest.raises(ValueError):
        adapters.to_minor("1.005", "USD")


def test_ledger_and_processor_adapters_keep_raw():
    l = adapters.ledger_line({"entry_id": "e1", "posted_date": "2026-11-02", "amount": "10.00",
                              "currency": "usd", "reference": "R", "memo": "m", "payout_ref": "P1"})
    p = adapters.processor_line({"txn_id": "t1", "date": "2026-11-02", "amount": "1.50",
                                 "currency": "USD", "type": "fee", "payout_id": "P1"})
    assert (l.amount_minor, l.currency, l.group, l.raw["memo"]) == (1000, "USD", "P1", "m")
    assert (p.kind, p.amount_minor) == ("fee", 150)
    with pytest.raises(ValueError):
        adapters.processor_line({"txn_id": "t", "date": "2026-11-02", "amount": "1",
                                 "currency": "USD", "type": "refund"})


def test_run_record_is_immutable_and_dashboard_renders(tmp_path):
    cfg = Config(as_of=date(2026, 11, 9))
    ours = [adapters.ledger_line({"entry_id": "<e1>", "posted_date": "2026-10-01", "amount": "5.00",
                                  "currency": "USD"})]
    r = reconcile(ours, [], cfg)
    rec = store.build_record(ours, [], cfg, r, datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc))
    path = store.write_record(tmp_path, rec)
    with pytest.raises(FileExistsError):
        store.write_record(tmp_path, rec)
    assert not path.stat().st_mode & 0o222
    html = dashboard.render(store.load_records(tmp_path))
    assert "&lt;e1&gt;" in html and "<e1>" not in html   # escaped
    assert "Oldest open break" in html
