"""Tests for triage signal classification logic."""
from support_ai.triage import infer_issue_category, infer_urgency_tier


def test_sso_category_detected():
    cat, _ = infer_issue_category("SSO login broken for all SAML users")
    assert cat == "authentication_sso"


def test_billing_category_detected():
    cat, _ = infer_issue_category("Invoice charged twice for subscription renewal")
    assert cat == "billing_plans"


def test_api_category_detected():
    cat, _ = infer_issue_category("Webhook endpoint returning 500 on POST payload")
    assert cat == "integration_api"


def test_p1_outage_detected():
    tier, _ = infer_urgency_tier("Production down — complete outage for all users")
    assert tier == "P1"


def test_p4_question_not_p1():
    tier, _ = infer_urgency_tier("How do I configure SSO? Just a question, not urgent")
    assert tier not in ("P1", "P2")


def test_unknown_category_fallback():
    cat, _ = infer_issue_category("random gibberish with absolutely no signals")
    assert cat == "unknown"


def test_urgency_returns_reasons():
    _, reasons = infer_urgency_tier("production down for all users")
    assert any("urgency signals" in r for r in reasons)
