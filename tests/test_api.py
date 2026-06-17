from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from support_ai.api import app
from support_ai.account_brief import AccountDataUnavailable, AccountNotFound
from support_ai.schemas import DataHealth, TriageOutput

client = TestClient(app)


# ── Test 1: /health returns 200 ───────────────────────────────────────────────


def test_health_200() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "zycus-support-ai"


# ── Test 2: /triage returns structured TriageOutput ──────────────────────────


def test_triage_returns_structured_output() -> None:
    resp = client.post("/triage", json={"subject": "SSO login failing", "body": "Cannot log in"})
    assert resp.status_code == 200
    data = resp.json()
    assert "urgency_tier" in data
    assert "issue_category" in data
    assert "recommended_team" in data
    assert "draft_response" in data
    assert "confidence" in data


def test_triage_text_field_accepted() -> None:
    resp = client.post("/triage", json={"text": "SSO login is failing for all production users"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["urgency_tier"] in ("P1", "P2", "P3", "P4")


# ── Test 3: /data-health returns expected shape ───────────────────────────────


def test_data_health_returns_expected_shape() -> None:
    resp = client.get("/data-health")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts_exists" in data
    assert "tickets_exists" in data
    assert "accounts_count" in data
    assert "tickets_count" in data
    assert "ready_for_account_briefs" in data


# ── Test 4: Missing account data returns 503 ─────────────────────────────────


def test_missing_account_data_returns_503() -> None:
    with patch(
        "support_ai.api.generate_account_brief",
        side_effect=AccountDataUnavailable("accounts.json missing"),
    ):
        resp = client.get("/accounts/A1/brief")
    assert resp.status_code == 503
    data = resp.json()
    assert "detail" in data


def test_account_not_found_returns_404() -> None:
    with patch(
        "support_ai.api.generate_account_brief",
        side_effect=AccountNotFound("Account A99 not found"),
    ):
        resp = client.get("/accounts/A99/brief")
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data


# ── Test 5: Error responses do not leak stack traces ─────────────────────────


def test_error_responses_do_not_leak_stack_traces() -> None:
    with patch(
        "support_ai.api.generate_account_brief",
        side_effect=AccountDataUnavailable("data missing"),
    ):
        resp = client.get("/accounts/BAD/brief")
    body_text = resp.text
    assert "Traceback" not in body_text
    assert "File " not in body_text
    assert "line " not in body_text
