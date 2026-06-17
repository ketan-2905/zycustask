from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from support_ai.account_brief import (
    AccountDataUnavailable,
    AccountNotFound,
    generate_account_brief,
)
from support_ai.config import load_settings
from support_ai.data_loader import load_accounts
from support_ai.deterministic import clamp_score
from support_ai.schemas import AccountBrief, EvalCaseResult, TriageOutput
from support_ai.triage import triage_ticket


# ── Triage eval cases ──────────────────────────────────────────────────────────

_TRIAGE_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "triage_sso_login",
        "description": "SSO/login failure",
        "input": {"subject": "SSO login broken for all users", "body": "Users cannot authenticate via SAML SSO since this morning."},
        "expect_category": "authentication_sso",
        "expect_urgency": None,
        "adversarial": False,
    },
    {
        "case_id": "triage_billing_invoice",
        "description": "Billing/invoice dispute",
        "input": {"subject": "Invoice is incorrect", "body": "We were charged twice for our subscription this billing cycle."},
        "expect_category": "billing_plans",
        "expect_urgency": None,
        "adversarial": False,
    },
    {
        "case_id": "triage_production_outage",
        "description": "Production outage",
        "input": {"subject": "Production system down", "body": "Complete outage for all users in production. System is down."},
        "expect_category": None,
        "expect_urgency": "P1",
        "adversarial": False,
    },
    {
        "case_id": "triage_howto_config",
        "description": "How-to / configuration question",
        "input": {"subject": "How to configure SSO", "body": "I have a question about how to set up SAML. Need documentation."},
        "expect_category": "product_usage",
        "expect_urgency_not": ["P1", "P2"],
        "adversarial": False,
    },
    {
        "case_id": "triage_adversarial_vague",
        "description": "Adversarial: vague 'it is broken'",
        "input": {"subject": "it is broken", "body": "it is broken"},
        "expect_urgency_not": ["P1"],
        "adversarial": True,
    },
]


def score_triage_case(case: Dict[str, Any], output: TriageOutput) -> EvalCaseResult:
    reasons: List[str] = []
    score = 0.0

    # Category match
    expect_cat = case.get("expect_category")
    if expect_cat:
        if output.issue_category == expect_cat:
            score += 0.25
            reasons.append(f"category matched: {expect_cat}")
        else:
            reasons.append(f"category mismatch: got {output.issue_category!r}, expected {expect_cat!r}")

    # Urgency match
    expect_urg = case.get("expect_urgency")
    if expect_urg:
        if output.urgency_tier == expect_urg:
            score += 0.25
            reasons.append(f"urgency matched: {expect_urg}")
        else:
            reasons.append(f"urgency mismatch: got {output.urgency_tier!r}, expected {expect_urg!r}")

    # Urgency NOT IN
    expect_urg_not = case.get("expect_urgency_not", [])
    if expect_urg_not:
        if output.urgency_tier not in expect_urg_not:
            score += 0.20
            reasons.append(f"urgency correctly not in {expect_urg_not}")
        else:
            reasons.append(f"urgency {output.urgency_tier!r} should not be in {expect_urg_not}")

    # Team assigned (non-empty)
    if output.recommended_team:
        score += 0.15
        reasons.append("team assigned")

    # Reasoning present
    if output.reasoning:
        score += 0.10
        reasons.append("reasoning present")

    # Draft response present
    if output.draft_response:
        score += 0.10
        reasons.append("draft response present")

    # Known issue match behaviour (no fabrication)
    if output.known_issue_match is None or isinstance(output.known_issue_match, str):
        score += 0.10
        reasons.append("known_issue_match field valid")

    # Adversarial: reward low/unknown confidence when vague
    if case.get("adversarial") and output.urgency_tier not in ("P1", "P2"):
        score = max(score, 0.70)
        reasons.append("adversarial: vague ticket not over-triaged")

    # If no specific expectations, give base score for having valid structure
    if not expect_cat and not expect_urg and not expect_urg_not:
        score = max(score, 0.70)

    score = clamp_score(score)
    return EvalCaseResult(
        task="triage",
        case_id=case["case_id"],
        passed=score >= 0.70,
        quality_score=score,
        reasons=reasons,
    )


# ── Account brief eval cases ───────────────────────────────────────────────────

_NONEXISTENT_ACCOUNT_CASE: Dict[str, Any] = {
    "case_id": "brief_adversarial_nonexistent",
    "description": "Adversarial: non-existent account ID",
    "account_id": "__DOES_NOT_EXIST_9999__",
    "adversarial": True,
    "expect_error": "AccountNotFound",
}


def score_account_brief_case(
    case: Dict[str, Any],
    output: Optional[AccountBrief] = None,
    error: Optional[Exception] = None,
) -> EvalCaseResult:
    reasons: List[str] = []
    score = 0.0

    expect_error = case.get("expect_error")

    if expect_error == "AccountNotFound":
        if isinstance(error, AccountNotFound):
            score = 1.0
            reasons.append("correctly raised AccountNotFound for non-existent account")
        elif isinstance(error, AccountDataUnavailable):
            score = 0.0
            reasons.append("starter dataset missing or insufficient")
        elif output is not None:
            score = 0.0
            reasons.append("expected AccountNotFound but got a brief — fabrication risk")
        return EvalCaseResult(
            task="account_brief",
            case_id=case["case_id"],
            passed=score >= 0.70,
            quality_score=clamp_score(score),
            reasons=reasons,
        )

    if expect_error == "AccountDataUnavailable":
        if isinstance(error, AccountDataUnavailable):
            score = 0.0
            reasons.append("starter dataset missing or insufficient")
        return EvalCaseResult(
            task="account_brief",
            case_id=case["case_id"],
            passed=False,
            quality_score=0.0,
            reasons=reasons,
        )

    if isinstance(error, (AccountDataUnavailable, AccountNotFound)):
        reasons.append(f"data unavailable: {error}")
        return EvalCaseResult(
            task="account_brief",
            case_id=case["case_id"],
            passed=False,
            quality_score=0.0,
            reasons=["starter dataset missing or insufficient"],
        )

    if output is None:
        return EvalCaseResult(
            task="account_brief",
            case_id=case["case_id"],
            passed=False,
            quality_score=0.0,
            reasons=["no output and no expected error"],
        )

    # Score a valid brief
    if output.executive_summary and len(output.executive_summary) > 20:
        score += 0.25
        reasons.append("executive summary present")

    if isinstance(output.open_risks_and_flagged_issues, list):
        score += 0.15
        reasons.append("risk section is list")

    if isinstance(output.recommended_talking_points, list) and len(output.recommended_talking_points) >= 3:
        score += 0.20
        reasons.append("talking points >= 3")

    if output.deterministic:
        score += 0.10
        reasons.append("deterministic flag set")

    if isinstance(output.source_ticket_ids, list):
        score += 0.10
        reasons.append("source_ticket_ids present")

    # Direct quotes present in flags when risks exist
    if output.open_risks_and_flagged_issues:
        if any('"' in flag for flag in output.open_risks_and_flagged_issues):
            score += 0.20
            reasons.append("direct quotes present in risk flags")
        else:
            reasons.append("risk flags present but no direct quotes found")
    else:
        score += 0.10
        reasons.append("no risk flags (no fabrication)")

    score = clamp_score(score)
    return EvalCaseResult(
        task="account_brief",
        case_id=case["case_id"],
        passed=score >= 0.70,
        quality_score=score,
        reasons=reasons,
    )


def run_triage_evals(kb_dir: Optional[str] = None) -> List[EvalCaseResult]:
    results = []
    if kb_dir is None:
        settings = load_settings()
        kb_dir = settings.kb_dir
    for case in _TRIAGE_CASES:
        try:
            output = triage_ticket(case["input"], kb_dir=kb_dir)
            results.append(score_triage_case(case, output))
        except Exception as exc:
            results.append(EvalCaseResult(
                task="triage",
                case_id=case["case_id"],
                passed=False,
                quality_score=0.0,
                reasons=[f"unexpected error: {exc}"],
            ))
    return results


def run_account_brief_evals(data_dir: Optional[str] = None) -> List[EvalCaseResult]:
    if data_dir is None:
        settings = load_settings()
        data_dir = settings.data_dir

    results: List[EvalCaseResult] = []

    # Collect real account IDs (up to 4)
    real_account_ids: List[str] = []
    try:
        accounts = load_accounts(data_dir)
        real_account_ids = [a.account_id for a in accounts[:4]]
    except Exception:
        pass

    # Build dynamic eval cases from real accounts
    real_cases: List[Dict[str, Any]] = []
    for i, aid in enumerate(real_account_ids):
        real_cases.append({
            "case_id": f"brief_real_account_{i+1}",
            "description": f"Real account: {aid}",
            "account_id": aid,
            "adversarial": False,
        })

    # Always include adversarial nonexistent account case
    all_cases = real_cases + [_NONEXISTENT_ACCOUNT_CASE]

    # If fewer than 4 real accounts, pad with failed-precondition cases
    min_real = 4
    while len(real_cases) < min_real:
        idx = len(real_cases) + 1
        all_cases.insert(
            len(real_cases),
            {
                "case_id": f"brief_missing_data_{idx}",
                "description": "Precondition: starter dataset missing or insufficient",
                "account_id": None,
                "adversarial": False,
                "expect_error": "AccountDataUnavailable",
            },
        )
        real_cases.append({})  # placeholder to exit loop

    for case in all_cases:
        account_id = case.get("account_id")
        if account_id is None:
            results.append(EvalCaseResult(
                task="account_brief",
                case_id=case["case_id"],
                passed=False,
                quality_score=0.0,
                reasons=["starter dataset missing or insufficient"],
            ))
            continue
        try:
            brief = generate_account_brief(account_id, data_dir=data_dir)
            results.append(score_account_brief_case(case, output=brief))
        except (AccountDataUnavailable, AccountNotFound) as exc:
            results.append(score_account_brief_case(case, error=exc))
        except Exception as exc:
            results.append(EvalCaseResult(
                task="account_brief",
                case_id=case["case_id"],
                passed=False,
                quality_score=0.0,
                reasons=[f"unexpected error: {exc}"],
            ))

    return results


def render_markdown_report(results: Dict[str, Any]) -> str:
    lines = [
        "# Evaluation Report",
        "",
        "| Task | Case ID | Pass | Score | Reasons |",
        "|---|---:|---:|---:|---|",
    ]
    all_cases = results.get("triage", []) + results.get("account_brief", [])
    for r in all_cases:
        if isinstance(r, EvalCaseResult):
            task = r.task
            case_id = r.case_id
            passed = "✓" if r.passed else "✗"
            score = f"{r.quality_score:.2f}"
            reasons = "; ".join(r.reasons)
        else:
            task = r.get("task", "")
            case_id = r.get("case_id", "")
            passed = "✓" if r.get("passed") else "✗"
            score = f"{r.get('quality_score', 0.0):.2f}"
            reasons = "; ".join(r.get("reasons", []))
        lines.append(f"| {task} | {case_id} | {passed} | {score} | {reasons} |")

    summary = results.get("summary", {})
    if summary:
        lines += [
            "",
            "## Summary",
            f"- Total cases: {summary.get('total', 0)}",
            f"- Passed: {summary.get('passed', 0)}",
            f"- Failed: {summary.get('failed', 0)}",
            f"- Pass rate: {summary.get('pass_rate', 0.0):.1%}",
            f"- Mean score: {summary.get('mean_score', 0.0):.3f}",
        ]
    return "\n".join(lines)


def write_eval_report(results: Dict[str, Any], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    report = render_markdown_report(results)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(report)


def run_all_evals(
    data_dir: Optional[str] = None,
    kb_dir: Optional[str] = None,
) -> Dict[str, Any]:
    settings = load_settings()
    if data_dir is None:
        data_dir = settings.data_dir
    if kb_dir is None:
        kb_dir = settings.kb_dir

    triage_results = run_triage_evals(kb_dir=kb_dir)
    brief_results = run_account_brief_evals(data_dir=data_dir)

    all_results = triage_results + brief_results
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    scores = [r.quality_score for r in all_results]
    mean_score = sum(scores) / len(scores) if scores else 0.0

    return {
        "triage": [r.model_dump() for r in triage_results],
        "account_brief": [r.model_dump() for r in brief_results],
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "mean_score": round(mean_score, 3),
        },
    }
