from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from support_ai.config import Settings, load_settings
from support_ai.deterministic import clamp_score, normalise_text
from support_ai.kb_retrieval import load_knowledge_docs, retrieve_docs
from support_ai.schemas import RetrievalMatch, TicketInput, TriageOutput

# ── Category signals ───────────────────────────────────────────────────────────

_CATEGORY_SIGNALS: Dict[str, List[str]] = {
    "authentication_sso": [
        "login", "sso", "saml", "oauth", "password", "token", "mfa", "2fa",
        "auth", "authentication", "sign in", "logout", "session", "credential",
    ],
    "billing_plans": [
        "invoice", "billing", "plan", "subscription", "renewal", "payment",
        "charge", "credit", "bill", "pricing",
    ],
    "performance_latency": [
        "slow", "latency", "timeout", "500", "503", "degraded", "outage",
        "performance", "lag", "unresponsive",
    ],
    "integration_api": [
        "api", "webhook", "integration", "connector", "endpoint", "payload", "sdk",
    ],
    "data_sync": [
        "sync", "missing data", "stale", "duplicate", "import", "export", "replication",
    ],
    "security_access": [
        "permission", "access denied", "role", "rbac", "admin", "unauthorized", "secret",
    ],
    "product_usage": [
        "how to", "how do", "configure", "setup", "documentation", "question", "guide",
    ],
}

# ── Urgency signals (P1 first — first tier with any hit wins) ─────────────────

_P1_SIGNALS = [
    "outage", "production down", "all users", "all production users",
    "production users", "all production", "data loss", "breach",
    "executive escalation", "system down", "service down", "complete failure",
    "down for everyone", "critical outage", "broken for all",
]
_P2_SIGNALS = [
    "major feature", "multiple users", "many users", "high business impact",
    "urgent escalation", "team cannot", "degraded", "severely impacted",
    "blocking multiple",
]
_P3_SIGNALS = [
    "single user", "one user", "workaround", "just me", "only me", "intermittent",
]
_P4_SIGNALS = [
    "how to", "how do", "question", "documentation", "enhancement",
    "cosmetic", "wondering", "not urgent", "low priority", "when possible",
]

_URGENCY_TIERS: List[Tuple[str, List[str]]] = [
    ("P1", _P1_SIGNALS),
    ("P2", _P2_SIGNALS),
    ("P3", _P3_SIGNALS),
    ("P4", _P4_SIGNALS),
]

# ── Broad product area inference ───────────────────────────────────────────────

_BROAD_PRODUCT_SIGNALS: Dict[str, List[str]] = {
    "billing": ["billing", "invoice", "payment", "subscription", "charge", "credit"],
    "authentication": ["login", "sso", "oauth", "saml", "mfa", "auth", "authentication"],
    "integrations": ["api", "webhook", "integration", "connector", "endpoint", "sdk"],
    "security": ["permission", "rbac", "unauthorized", "breach", "secret"],
}

# ── Follow-up questions per category ──────────────────────────────────────────

_FOLLOW_UP: Dict[str, str] = {
    "authentication_sso": (
        "Could you share the exact error message and the browser or client being used?"
    ),
    "billing_plans": (
        "Could you confirm the affected account name and the invoice or subscription ID in question?"
    ),
    "performance_latency": (
        "Could you provide the affected service or endpoint name, along with relevant timestamps or error codes?"
    ),
    "integration_api": (
        "Could you share the API endpoint, HTTP method, and a redacted version of the request/response payload?"
    ),
    "data_sync": (
        "Could you specify which dataset or integration is affected and when the issue first appeared?"
    ),
    "security_access": (
        "Could you provide the affected user's role, the resource they are trying to access, and the error they receive?"
    ),
    "product_usage": (
        "Could you describe your current setup and the specific step where you are facing difficulty?"
    ),
}

# ── Internal helpers ───────────────────────────────────────────────────────────


def _signal_hits(text: str, signals: List[str]) -> List[str]:
    normalised = normalise_text(text)
    matched = []
    for sig in signals:
        pattern = r"\b" + re.escape(normalise_text(sig)) + r"\b"
        if re.search(pattern, normalised):
            matched.append(sig)
    return matched


# ── Public helpers ─────────────────────────────────────────────────────────────


def normalize_ticket_input(ticket: Any) -> TicketInput:
    if isinstance(ticket, TicketInput):
        return ticket
    if isinstance(ticket, dict):
        subject = str(ticket.get("subject") or ticket.get("title") or "")
        body = str(
            ticket.get("body") or ticket.get("description") or ticket.get("text") or ""
        )
        return TicketInput(subject=subject, body=body, raw=json.dumps(ticket))
    text = str(ticket)
    return TicketInput(subject=text[:200], body=text, raw=text)


def infer_issue_category(text: str) -> Tuple[str, List[str]]:
    best_cat, best_count, best_matched = "unknown", 0, []
    for category, signals in _CATEGORY_SIGNALS.items():
        matched = _signal_hits(text, signals)
        if len(matched) > best_count:
            best_count = len(matched)
            best_cat = category
            best_matched = matched
    reasons = [f"category signals: {', '.join(best_matched)}"] if best_matched else []
    return best_cat, reasons


def infer_urgency_tier(text: str) -> Tuple[str, List[str]]:
    for tier, signals in _URGENCY_TIERS:
        matched = _signal_hits(text, signals)
        if matched:
            return tier, [f"urgency signals: {', '.join(matched)}"]
    return "P3", ["default urgency: no strong signals detected"]


def infer_product_area(
    text: str, matches: List[RetrievalMatch]
) -> Tuple[str, List[str]]:
    for match in matches:
        parts = Path(match.path).parts
        for i, part in enumerate(parts):
            if part == "products" and i + 1 < len(parts):
                product = Path(parts[i + 1]).stem
                return product, [f"KB match under products/: {match.path}"]

    for area, signals in _BROAD_PRODUCT_SIGNALS.items():
        matched = _signal_hits(text, signals)
        if matched:
            return area, [f"text signals product area '{area}': {', '.join(matched)}"]

    return "unknown", ["no product area signals detected"]


def recommend_team(
    product_area: str, issue_category: str, urgency_tier: str
) -> str:
    if urgency_tier == "P1" and issue_category == "security_access":
        return "Security Incident Response"
    if urgency_tier == "P1" and issue_category == "performance_latency":
        return "Platform On-Call / SRE"
    if issue_category == "billing_plans":
        return "Billing Support"
    if issue_category == "authentication_sso":
        return "Identity & Access Support"
    if issue_category == "integration_api":
        return "Integrations Support"
    if issue_category == "performance_latency":
        return "Platform Support"
    if issue_category == "product_usage":
        return "Tier-1 Product Support"
    return "Tier-2 Support Triage"


def draft_first_response(ticket: TicketInput, output_without_draft: TriageOutput) -> str:
    subject = ticket.subject or "your recent inquiry"
    urgency = output_without_draft.urgency_tier
    team = output_without_draft.recommended_team
    category = output_without_draft.issue_category

    acknowledgment = (
        f"Thank you for contacting support. We have received your ticket"
        f" regarding: {subject}."
    )
    routing = (
        f"Your issue has been classified as {urgency} priority and assigned to {team}."
    )
    question = _FOLLOW_UP.get(
        category,
        "Could you provide any additional context or error messages to help us investigate?",
    )
    return f"{acknowledgment}\n\n{routing}\n\n{question}"


# ── Main entry point ───────────────────────────────────────────────────────────


def triage_ticket(
    ticket: Any,
    kb_dir: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> TriageOutput:
    if settings is None:
        settings = load_settings()

    ticket_input = normalize_ticket_input(ticket)
    combined = f"{ticket_input.subject}\n{ticket_input.body}"

    docs = load_knowledge_docs(kb_dir) if kb_dir else []
    matches = retrieve_docs(combined, docs, top_k=3, min_score=0.08)

    issue_category, cat_reasons = infer_issue_category(combined)
    urgency_tier, urg_reasons = infer_urgency_tier(combined)
    product_area, prod_reasons = infer_product_area(combined, matches)
    recommended_team = recommend_team(product_area, issue_category, urgency_tier)

    confidence = 0.35
    if issue_category != "unknown":
        confidence += 0.20
    if product_area != "unknown":
        confidence += 0.15
    if matches:
        confidence += 0.20
    if urgency_tier in ("P1", "P2"):
        confidence += 0.10
    confidence = clamp_score(confidence)

    reasoning = "; ".join(cat_reasons + urg_reasons + prod_reasons)
    if not reasoning:
        reasoning = "No strong classification signals detected."

    partial = TriageOutput(
        product_area=product_area,
        issue_category=issue_category,
        urgency_tier=urgency_tier,
        reasoning=reasoning,
        known_issue_match=matches[0].doc_id if matches else None,
        relevant_docs=matches,
        recommended_team=recommended_team,
        draft_response="",
        confidence=confidence,
    )

    draft = draft_first_response(ticket_input, partial)

    return TriageOutput(
        product_area=product_area,
        issue_category=issue_category,
        urgency_tier=urgency_tier,
        reasoning=reasoning,
        known_issue_match=matches[0].doc_id if matches else None,
        relevant_docs=matches,
        recommended_team=recommended_team,
        draft_response=draft,
        confidence=confidence,
    )
