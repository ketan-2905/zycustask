from __future__ import annotations

import json

import pytest

from support_ai.data_loader import (
    coerce_records,
    dataset_health,
    extract_first,
    get_tickets_for_account,
    load_accounts,
    load_tickets,
)


def _write(path, data):
    path.write_text(json.dumps(data))


# 1 — missing files return counts 0 and errors
def test_missing_files_return_zero_counts_and_errors(tmp_path):
    health = dataset_health(str(tmp_path))
    assert health.accounts_count == 0
    assert health.tickets_count == 0
    assert health.accounts_error is not None
    assert health.tickets_error is not None
    assert health.ready_for_account_briefs is False


# 2 — empty files return counts 0 and errors mentioning "empty"
def test_empty_files_return_empty_error(tmp_path):
    (tmp_path / "accounts.json").write_text("")
    (tmp_path / "tickets.json").write_text("")
    health = dataset_health(str(tmp_path))
    assert health.accounts_count == 0
    assert health.tickets_count == 0
    assert "empty" in (health.accounts_error or "").lower()
    assert "empty" in (health.tickets_error or "").lower()


# 3 — list-shaped JSON parses correctly
def test_list_shaped_json_parses(tmp_path):
    _write(tmp_path / "accounts.json", [
        {"account_id": "a1", "name": "Acme"},
        {"account_id": "a2", "name": "Beta"},
    ])
    _write(tmp_path / "tickets.json", [
        {"ticket_id": "t1", "account_id": "a1", "subject": "Bug", "body": "details"},
    ])
    accounts = load_accounts(str(tmp_path))
    tickets = load_tickets(str(tmp_path))
    assert len(accounts) == 2
    assert accounts[0].account_id == "a1"
    assert len(tickets) == 1
    assert tickets[0].subject == "Bug"


# 4 — dict-shaped {"accounts": [...]} and {"tickets": [...]} parse
def test_dict_shaped_json_parses(tmp_path):
    _write(tmp_path / "accounts.json", {
        "accounts": [{"account_id": "a1"}, {"account_id": "a2"}],
        "meta": {"total": 2},
    })
    _write(tmp_path / "tickets.json", {
        "tickets": [{"ticket_id": "t1", "account_id": "a1", "subject": "Login", "body": "fail"}],
    })
    accounts = load_accounts(str(tmp_path))
    tickets = load_tickets(str(tmp_path))
    assert len(accounts) == 2
    assert len(tickets) == 1


# 5 — case-insensitive key extraction
def test_case_insensitive_extraction():
    rec = {"AccountID": "X42", "Subject": "Hello", "BODY": "world"}
    assert extract_first(rec, ["account_id", "accountid"]) == "X42"
    assert extract_first(rec, ["subject", "title"]) == "Hello"
    assert extract_first(rec, ["body", "description"]) == "world"


# 6 — invalid JSON does not crash
def test_invalid_json_does_not_crash(tmp_path):
    (tmp_path / "accounts.json").write_text("{not: valid json!!!")
    (tmp_path / "tickets.json").write_text("[broken")
    health = dataset_health(str(tmp_path))
    assert health.accounts_count == 0
    assert health.tickets_count == 0
    assert health.accounts_error is not None
    assert "invalid" in health.accounts_error.lower()


# 7 — get_tickets_for_account filters by account_id
def test_get_tickets_for_account_filters_correctly(tmp_path):
    _write(tmp_path / "accounts.json", [{"account_id": "a1"}, {"account_id": "a2"}])
    _write(tmp_path / "tickets.json", [
        {"ticket_id": "t1", "account_id": "a1", "subject": "s1", "body": "b1"},
        {"ticket_id": "t2", "account_id": "a2", "subject": "s2", "body": "b2"},
        {"ticket_id": "t3", "account_id": "a1", "subject": "s3", "body": "b3"},
    ])
    result = get_tickets_for_account(str(tmp_path), "a1")
    assert len(result) == 2
    assert all(t.account_id == "a1" for t in result)
    assert {t.ticket_id for t in result} == {"t1", "t3"}
