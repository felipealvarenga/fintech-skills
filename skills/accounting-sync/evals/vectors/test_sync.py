"""Test vectors for accounting-sync.

Run against the reference: `pytest skills/accounting-sync`.
Run against your module:   `SYNC_SOLUTION=/path/to/sync.py pytest skills/accounting-sync`.

The module under test must expose FakeAccounting, Sync, TokenStore, StaleToken, PeriodClosed
and drift_report as used below.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date
from pathlib import Path

import pytest


def _load():
    path = os.environ.get("SYNC_SOLUTION") or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location("sync_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
MAP = {"acme": {"sales": "4010", "fees": "5010", "receivable": "1020"}}
DAY = date(2026, 6, 3)
LINES = [
    {"account": "receivable", "side": "debit", "amount_minor": 9710},
    {"account": "fees", "side": "debit", "amount_minor": 290},
    {"account": "sales", "side": "credit", "amount_minor": 10000},
]


def test_push_is_idempotent_and_updates_on_change():
    remote = m.FakeAccounting()
    sync = m.Sync(remote, MAP)
    assert sync.push_summary("acme", DAY, LINES) == "created"
    assert sync.push_summary("acme", DAY, LINES) == "unchanged"
    assert len(remote.objects) == 1
    changed = LINES[:2] + [{"account": "sales", "side": "credit", "amount_minor": 10001}]
    assert sync.push_summary("acme", DAY, changed) == "updated"
    assert len(remote.objects) == 1
    assert remote.objects["je_1"]["token"] == 1


def test_request_id_dedupes_a_create_whose_response_was_lost():
    remote = m.FakeAccounting()
    sync = m.Sync(remote, MAP)
    sync.push_summary("acme", DAY, LINES)
    sync.pairs.clear()  # our side lost the pair, as after a crash before persisting it
    assert sync.push_summary("acme", DAY, LINES) == "created"
    assert len(remote.objects) == 1  # the accounting system returned the original object


def test_unmapped_account_is_queued_not_guessed():
    remote = m.FakeAccounting()
    sync = m.Sync(remote, MAP)
    lines = LINES + [{"account": "mystery", "side": "debit", "amount_minor": 1}]
    assert sync.push_summary("acme", DAY, lines) == "queued_unmapped"
    assert len(remote.objects) == 0 and sync.unmapped[0]["account"] == "mystery"


def test_stale_token_with_unchanged_remote_is_retried():
    remote = m.FakeAccounting()
    sync = m.Sync(remote, MAP)
    sync.push_summary("acme", DAY, LINES)
    remote.objects["je_1"]["token"] += 1  # the token moved without a content change
    changed = LINES[:2] + [{"account": "sales", "side": "credit", "amount_minor": 10001}]
    assert sync.push_summary("acme", DAY, changed) == "updated"
    assert sync.conflicts == []


@pytest.mark.parametrize("policy,expected_status,remote_memo_after", [
    ("flag", "conflict", "accountant note"),
    ("theirs_wins", "conflict", "accountant note"),
    ("ours_wins", "updated", "acme daily summary 2026-06-03"),
])
def test_remote_edit_is_never_overwritten_silently(policy, expected_status, remote_memo_after):
    remote = m.FakeAccounting()
    sync = m.Sync(remote, MAP, conflict_policy=policy)
    sync.push_summary("acme", DAY, LINES)
    remote.edit_remotely("je_1", memo="accountant note")
    changed = LINES[:2] + [{"account": "sales", "side": "credit", "amount_minor": 10001}]
    assert sync.push_summary("acme", DAY, changed) == expected_status
    assert len(sync.conflicts) == 1 and sync.conflicts[0]["policy"] == policy
    assert remote.objects["je_1"]["memo"] == remote_memo_after


def test_closed_period_posts_in_the_open_period_with_the_original_date_in_the_memo():
    remote = m.FakeAccounting(closed_through=date(2026, 6, 30))
    sync = m.Sync(remote, MAP)
    with pytest.raises(m.PeriodClosed):
        sync.push_summary("acme", DAY, LINES)
    status = sync.push_summary("acme", DAY, LINES, first_open_day=date(2026, 7, 1))
    assert status == "created"
    obj = remote.objects["je_1"]
    assert obj["date"] == date(2026, 7, 1) and "original date 2026-06-03" in obj["memo"]
    assert sync.posted_in_open_period == [{"tenant": "acme", "day": DAY, "posted": date(2026, 7, 1)}]


def test_amounts_convert_to_major_units_at_the_edge():
    remote = m.FakeAccounting()
    sync = m.Sync(remote, MAP)
    sync.push_summary("acme", DAY, LINES)
    lines = remote.objects["je_1"]["lines"]
    assert [l["amount"] for l in lines] == ["97.10", "2.90", "100.00"]
    assert [l["account"] for l in lines] == ["1020", "5010", "4010"]


def test_rotated_refresh_token_is_persisted_before_the_next_call():
    store = m.TokenStore(refresh_token="rt_1")

    def endpoint(refresh_token):
        assert refresh_token == "rt_1"
        return {"access_token": "at_2", "refresh_token": "rt_2", "x_refresh_token_expires_at": "2027-01-01T00:00:00Z"}

    access = store.refresh(endpoint)
    assert access == "at_2" and store.refresh_token == "rt_2" and store.expires_at == "2027-01-01T00:00:00Z"
    assert store.history == ["rt_1"]

    def failing_api(token):
        raise RuntimeError("503")

    with pytest.raises(RuntimeError):
        failing_api(access)
    assert store.refresh_token == "rt_2"  # the rotation survived the failed call


def test_drift_report_flags_one_cent():
    ours = {"4010": -1_000_000, "5010": 29_000, "1020": 971_000}
    theirs = {"4010": -1_000_000, "5010": 29_001, "1020": 971_000, "9999": 5}
    rows = m.drift_report(ours, theirs)
    assert rows == [{"account": "5010", "ours": 29_000, "theirs": 29_001, "diff": -1},
                    {"account": "9999", "ours": 0, "theirs": 5, "diff": -5}]
    assert m.drift_report(ours, theirs, threshold_minor=10) == []
