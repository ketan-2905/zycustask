from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from support_ai.account_brief import (
    AccountDataUnavailable,
    AccountNotFound,
    detect_risk_flags,
    filter_last_90_days,
    generate_account_brief,
    compute_as_of,
    extract_direct_quote,
)
from support_ai.schemas import LoadedTicket


# ── Helpers ────────────────────────────────────────────────────────────────────


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _data_dir(tmp_path: Path, accounts: object, tickets: object) -> str:
    d = tmp_path / "data"
    d.mkdir()
    _write(d / "accounts.json", accounts)
    _write(d / "tickets.json", tickets)
    return str(d)


def _acct(aid: str, **kwargs: object) -> dict:
    return {"account_id": aid, "name": f"Company {aid}", **kwargs}


def _ticket(tid: str, aid: str, subject: str, body: str = "", date: str | None = "2024-01-10") -> dict:
    return {
        "ticket_id": tid,
        "account_id": aid,
        "subject": subject,
        "body": body,
        "created_at": date,
        "status": "open",
        "priority": "medium",
    }


# ── Test 1: Missing data raises AccountDataUnavailable ─────────────────────────


def test_missing_accounts_raises_unavailable(tmp_path: Path) -> None:
    d = tmp_path / "empty"
    d.mkdir()
    # tickets exists but accounts does not
    _write(d / "tickets.json", [])
    with pytest.raises(AccountDataUnavailable):
        generate_account_brief("A1", data_dir=str(d))


# ── Test 2: Unknown account raises AccountNotFound ────────────────────────────


def test_unknown_account_raises_not_found(tmp_path: Path) -> None:
    dd = _data_dir(tmp_path, [_acct("A1")], [])
    with pytest.raises(AccountNotFound):
        generate_account_brief("DOES_NOT_EXIST", data_dir=dd)


# ── Test 3: Valid account returns all 3 sections ──────────────────────────────


def test_valid_account_returns_all_sections(tmp_path: Path) -> None:
    dd = _data_dir(
        tmp_path,
        [_acct("A1")],
        [_ticket("T1", "A1", "SSO login failing for all users")],
    )
    brief = generate_account_brief("A1", data_dir=dd)
    assert brief.account_id == "A1"
    assert len(brief.executive_summary) > 20
    assert isinstance(brief.open_risks_and_flagged_issues, list)
    assert isinstance(brief.recommended_talking_points, list)
    assert 3 <= len(brief.recommended_talking_points) <= 6


# ── Test 4: Last 90 days uses max dataset date, not real today ────────────────


def test_90_day_window_uses_dataset_max_date(tmp_path: Path) -> None:
    # Max date in dataset is 2023-06-01; ticket dated 2023-01-01 is >90 days before that
    dd = _data_dir(
        tmp_path,
        [_acct("A1")],
        [
            _ticket("T_old", "A1", "old issue", date="2023-01-01"),
            _ticket("T_new", "A1", "recent issue", date="2023-06-01"),
        ],
    )
    brief = generate_account_brief("A1", data_dir=dd)
    # T_old (2023-01-01) is 151 days before 2023-06-01, so outside 90-day window
    assert "T_old" not in brief.source_ticket_ids
    assert "T_new" in brief.source_ticket_ids


# ── Test 5: Churn risk flagged with direct quote ──────────────────────────────


def test_churn_risk_flagged_with_quote(tmp_path: Path) -> None:
    dd = _data_dir(
        tmp_path,
        [_acct("A1")],
        [_ticket("T1", "A1", "We are considering a competitor", "We may cancel our subscription")],
    )
    brief = generate_account_brief("A1", data_dir=dd)
    assert any("churn_risk" in flag.lower() for flag in brief.open_risks_and_flagged_issues)
    # Quote must be present (non-empty string in flag)
    churn_flags = [f for f in brief.open_risks_and_flagged_issues if "churn_risk" in f.lower()]
    assert churn_flags
    assert '"' in churn_flags[0]  # contains a direct quote


# ── Test 6: Escalation flagged with direct quote ─────────────────────────────


def test_escalation_flagged_with_quote(tmp_path: Path) -> None:
    dd = _data_dir(
        tmp_path,
        [_acct("A1")],
        [_ticket("T2", "A1", "This is unacceptable, we need to escalate to executive")],
    )
    brief = generate_account_brief("A1", data_dir=dd)
    assert any("escalation" in flag.lower() for flag in brief.open_risks_and_flagged_issues)
    esc_flags = [f for f in brief.open_risks_and_flagged_issues if "escalation" in f.lower()]
    assert esc_flags
    assert '"' in esc_flags[0]


# ── Test 7: Incomplete account still produces brief ───────────────────────────


def test_incomplete_account_produces_brief(tmp_path: Path) -> None:
    # Account with only an ID, no name/tier/health/owner
    dd = _data_dir(
        tmp_path,
        [{"account_id": "BARE"}],
        [],
    )
    brief = generate_account_brief("BARE", data_dir=dd)
    assert brief.account_id == "BARE"
    assert len(brief.executive_summary) > 10
    assert len(brief.recommended_talking_points) >= 3


# ── Test 8: Same input returns identical output ───────────────────────────────


def test_deterministic_output(tmp_path: Path) -> None:
    dd = _data_dir(
        tmp_path,
        [_acct("A1")],
        [
            _ticket("T1", "A1", "We are considering cancellation"),
            _ticket("T2", "A1", "Production outage ongoing"),
        ],
    )
    fixed_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
    b1 = generate_account_brief("A1", data_dir=dd, as_of=fixed_date)
    b2 = generate_account_brief("A1", data_dir=dd, as_of=fixed_date)
    assert b1.model_dump() == b2.model_dump()


# ── Test 9: PII in quote is redacted ─────────────────────────────────────────


def test_pii_redacted_in_quote(tmp_path: Path) -> None:
    dd = _data_dir(
        tmp_path,
        [_acct("A1")],
        [_ticket("T1", "A1", "User john@example.com wants to cancel their account")],
    )
    brief = generate_account_brief("A1", data_dir=dd)
    full_text = " ".join(brief.open_risks_and_flagged_issues)
    assert "john@example.com" not in full_text
    assert "[EMAIL]" in full_text


# ── Test 10: Account with no tickets has no fake risks ────────────────────────


def test_no_tickets_produces_no_risks(tmp_path: Path) -> None:
    dd = _data_dir(tmp_path, [_acct("A1")], [])
    brief = generate_account_brief("A1", data_dir=dd)
    assert brief.open_risks_and_flagged_issues == []
    assert len(brief.recommended_talking_points) >= 3  # still produces talking points


# ── Unit: compute_as_of falls back correctly ──────────────────────────────────


def test_compute_as_of_uses_max_ticket_date() -> None:
    tickets = [
        LoadedTicket(
            ticket_id="t1", account_id="a", subject="s", body="b",
            created_at="2024-03-01", status="open", priority="P2", raw={}
        ),
        LoadedTicket(
            ticket_id="t2", account_id="a", subject="s", body="b",
            created_at="2024-01-01", status="open", priority="P3", raw={}
        ),
    ]
    as_of = compute_as_of(tickets)
    assert as_of.year == 2024 and as_of.month == 3 and as_of.day == 1


def test_filter_last_90_days_excludes_old_tickets() -> None:
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    tickets = [
        LoadedTicket(
            ticket_id="recent", account_id="a", subject="s", body="b",
            created_at="2024-05-01", status="open", priority="P2", raw={}
        ),
        LoadedTicket(
            ticket_id="old", account_id="a", subject="s", body="b",
            created_at="2024-01-01", status="open", priority="P3", raw={}
        ),
        LoadedTicket(
            ticket_id="nodates", account_id="a", subject="s", body="b",
            created_at=None, status="open", priority="P3", raw={}
        ),
    ]
    result = filter_last_90_days(tickets, as_of)
    ids = {t.ticket_id for t in result}
    assert "recent" in ids
    assert "old" not in ids
    assert "nodates" in ids  # undated tickets are always included
