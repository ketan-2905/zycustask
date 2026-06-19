from __future__ import annotations

import json
from pathlib import Path

from support_ai.account_brief import AccountDataUnavailable, AccountNotFound
from support_ai.evals import (
    _TRIAGE_CASES,
    render_markdown_report,
    run_account_brief_evals,
    run_all_evals,
    run_triage_evals,
    score_account_brief_case,
    score_triage_case,
)
from support_ai.schemas import EvalCaseResult

# ── Test 1: Triage evals return >= 5 results ─────────────────────────────────


def test_triage_evals_return_at_least_5_results() -> None:
    results = run_triage_evals()
    assert len(results) >= 5
    for r in results:
        assert isinstance(r, EvalCaseResult)
        assert r.task == "triage"


# ── Test 2: Adversarial triage case exists ────────────────────────────────────


def test_triage_adversarial_case_exists() -> None:
    adversarial = [c for c in _TRIAGE_CASES if c.get("adversarial")]
    assert adversarial, "At least one adversarial triage case must be defined"
    results = run_triage_evals()
    adv_ids = {c["case_id"] for c in adversarial}
    adv_results = [r for r in results if r.case_id in adv_ids]
    assert adv_results, "Adversarial triage case must appear in results"


# ── Test 3: Scores are between 0 and 1 ───────────────────────────────────────


def test_all_scores_clamped_0_to_1() -> None:
    results = run_all_evals()
    all_cases = results["triage"] + results["account_brief"]
    for r in all_cases:
        score = r["quality_score"]
        assert 0.0 <= score <= 1.0, f"Score out of range: {score} for {r['case_id']}"


# ── Test 4: Markdown report has table header ──────────────────────────────────


def test_markdown_report_has_table_header() -> None:
    results = run_all_evals()
    report = render_markdown_report(results)
    assert "| Task | Case ID | Pass | Score | Reasons |" in report
    assert "|---|" in report


# ── Test 5: Account evals return >= 5 results even when data missing ──────────


def test_account_brief_evals_return_at_least_5_results(tmp_path: Path) -> None:
    # Use a non-existent data dir to simulate missing data
    results = run_account_brief_evals(data_dir=str(tmp_path / "nonexistent"))
    assert len(results) >= 5
    for r in results:
        assert isinstance(r, EvalCaseResult)
        assert r.task == "account_brief"


# ── Test 6: Missing account case does not fabricate output ────────────────────


def test_nonexistent_account_does_not_fabricate(tmp_path: Path) -> None:
    dd = tmp_path / "data"
    dd.mkdir()
    (dd / "accounts.json").write_text(json.dumps([{"account_id": "REAL1", "name": "Real Corp"}]))
    (dd / "tickets.json").write_text(json.dumps([]))

    results = run_account_brief_evals(data_dir=str(dd))
    adv = [r for r in results if "nonexistent" in r.case_id or "adversarial" in r.case_id]
    assert adv, "Adversarial nonexistent-account case must be in results"
    # Should pass (correctly raises AccountNotFound, no brief fabricated)
    assert adv[0].passed


# ── Test 7: Summary counts are correct ───────────────────────────────────────


def test_summary_counts_correct() -> None:
    results = run_all_evals()
    summary = results["summary"]
    total = summary["total"]
    passed = summary["passed"]
    failed = summary["failed"]
    assert passed + failed == total
    all_cases = results["triage"] + results["account_brief"]
    assert len(all_cases) == total
    actual_passed = sum(1 for r in all_cases if r["passed"])
    assert actual_passed == passed


# ── Unit: score_triage_case produces correct EvalCaseResult ──────────────────


def test_score_triage_sso_case() -> None:
    from support_ai.triage import triage_ticket
    case = {
        "case_id": "test_sso",
        "input": {"subject": "SSO login broken", "body": "SAML auth not working"},
        "expect_category": "authentication_sso",
        "adversarial": False,
    }
    output = triage_ticket(case["input"])
    result = score_triage_case(case, output)
    assert isinstance(result, EvalCaseResult)
    assert result.task == "triage"
    assert 0.0 <= result.quality_score <= 1.0


def test_score_account_brief_not_found() -> None:
    case = {
        "case_id": "brief_notfound",
        "account_id": "GHOST",
        "adversarial": True,
        "expect_error": "AccountNotFound",
    }
    result = score_account_brief_case(case, error=AccountNotFound("not found"))
    assert result.passed
    assert result.quality_score == 1.0


def test_score_account_brief_data_unavailable_gives_zero() -> None:
    case = {
        "case_id": "brief_nodata",
        "account_id": None,
        "adversarial": False,
        "expect_error": "AccountDataUnavailable",
    }
    result = score_account_brief_case(case, error=AccountDataUnavailable("missing"))
    assert not result.passed
    assert result.quality_score == 0.0
    assert any("starter dataset" in r for r in result.reasons)
