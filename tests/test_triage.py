from __future__ import annotations

from pathlib import Path

from support_ai.schemas import TriageOutput
from support_ai.triage import triage_ticket


def _make_kb(tmp_path, structure: dict) -> str:
    kb = tmp_path / "kb"
    kb.mkdir()
    for rel, content in structure.items():
        p = kb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return str(kb)


# 1 — SSO ticket → authentication_sso
def test_sso_ticket_classified_as_authentication():
    result = triage_ticket({
        "subject": "SSO login failing",
        "body": "Cannot login via SSO authentication. SAML assertion error.",
    })
    assert result.issue_category == "authentication_sso"


# 2 — Billing ticket → billing_plans
def test_billing_ticket_classified_correctly():
    result = triage_ticket({
        "subject": "Invoice and billing question",
        "body": "Our subscription renewal shows an incorrect billing charge on the invoice.",
    })
    assert result.issue_category == "billing_plans"


# 3 — Outage text → P1
def test_outage_ticket_is_p1():
    result = triage_ticket({
        "subject": "Critical outage",
        "body": "Production outage — all users affected. System down, complete failure.",
    })
    assert result.urgency_tier == "P1"


# 4 — How-to question → P3/P4, never P1/P2
def test_howto_question_is_not_high_urgency():
    result = triage_ticket({
        "subject": "How to configure SSO settings",
        "body": (
            "Looking for documentation on how to set up single sign-on. "
            "Question about our setup guide."
        ),
    })
    assert result.urgency_tier in ("P3", "P4"), (
        f"Expected P3 or P4, got {result.urgency_tier}"
    )


# 5 — KB match surfaces doc path in relevant_docs
def test_kb_match_surfaces_doc_path(tmp_path):
    kb_dir = _make_kb(tmp_path, {
        "auth/sso.md": (
            "# SSO Authentication\n\n"
            "SSO login and authentication configuration guide.\n"
        ),
    })
    result = triage_ticket(
        {"subject": "SSO login problem", "body": "Cannot login via SSO authentication"},
        kb_dir=kb_dir,
    )
    assert len(result.relevant_docs) > 0, "Expected at least one KB match"
    assert result.known_issue_match is not None
    assert any("sso" in doc.path.lower() for doc in result.relevant_docs)


# 6 — Empty KB returns no match
def test_empty_kb_returns_no_match(tmp_path):
    kb_dir = str(tmp_path / "empty-kb")
    Path(kb_dir).mkdir()
    result = triage_ticket(
        {"subject": "SSO login failing", "body": "Cannot login via SSO"},
        kb_dir=kb_dir,
    )
    assert result.relevant_docs == []
    assert result.known_issue_match is None


# 7 — Dict subject/body input is normalised and processed
def test_dict_input_works():
    result = triage_ticket({
        "subject": "API webhook not firing",
        "body": (
            "Our webhook endpoint is not receiving payloads from the integration connector."
        ),
    })
    assert isinstance(result, TriageOutput)
    assert result.issue_category == "integration_api"
    assert result.draft_response != ""


# 8 — Adversarial ticket with low-urgency language does not over-escalate
def test_adversarial_ticket_does_not_over_escalate():
    result = triage_ticket({
        "subject": "Low priority documentation question",
        "body": (
            "Not urgent at all. I have a question about how to configure our plan. "
            "Low priority, no rush, just wondering when possible."
        ),
    })
    assert result.urgency_tier in ("P3", "P4"), (
        f"Adversarial ticket must not escalate above P3, got {result.urgency_tier}"
    )


# 9 — Draft response is non-empty and contains no fake ETA
def test_draft_response_non_empty_and_no_fake_eta():
    result = triage_ticket({
        "subject": "Login broken",
        "body": "Cannot login to the platform. Getting an authentication error.",
    })
    assert len(result.draft_response) > 50, "Draft response too short"
    draft_lower = result.draft_response.lower()
    forbidden = [
        "will be fixed in",
        "fix in 2",
        "resolve by",
        "estimated time",
        "eta:",
        "within 24 hours",
        "will be resolved",
        "will resolve",
    ]
    for phrase in forbidden:
        assert phrase not in draft_lower, (
            f"Draft should not contain fake ETA phrase: '{phrase}'"
        )
