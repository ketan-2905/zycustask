"""Integration tests for batch_triage convenience wrapper."""
from support_ai.triage import batch_triage


_TICKETS = [
    {"subject": "SSO broken", "body": "SAML login fails for all users in production"},
    {"subject": "Invoice wrong", "body": "We were charged twice for our subscription billing cycle"},
    {"subject": "API webhook down", "body": "POST /webhook endpoint returning 500 errors on payload"},
]


def test_batch_returns_correct_count():
    results = batch_triage(_TICKETS)
    assert len(results) == len(_TICKETS)


def test_batch_first_ticket_is_auth():
    results = batch_triage(_TICKETS)
    assert results[0].issue_category == "authentication_sso"


def test_batch_second_ticket_is_billing():
    results = batch_triage(_TICKETS)
    assert results[1].issue_category == "billing_plans"


def test_batch_all_have_recommended_team():
    results = batch_triage(_TICKETS)
    assert all(r.recommended_team for r in results)


def test_batch_all_have_draft_response():
    results = batch_triage(_TICKETS)
    assert all(r.draft_response for r in results)
