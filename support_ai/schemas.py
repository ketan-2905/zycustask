from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TicketInput(BaseModel):
    subject: str
    body: str
    raw: str


class KnowledgeDoc(BaseModel):
    doc_id: str
    path: str
    title: str
    category: str
    content: str


class RetrievalMatch(BaseModel):
    doc_id: str
    path: str
    title: str
    score: float
    snippet: str


class TriageOutput(BaseModel):
    product_area: str
    issue_category: str
    urgency_tier: str  # P1–P4
    reasoning: str
    known_issue_match: str | None = None
    relevant_docs: list[RetrievalMatch] = []
    recommended_team: str
    draft_response: str
    confidence: float


class AccountBrief(BaseModel):
    account_id: str
    executive_summary: str
    open_risks_and_flagged_issues: list[str]
    recommended_talking_points: list[str]
    source_ticket_ids: list[str]
    deterministic: bool = True


class EvalCaseResult(BaseModel):
    task: str
    case_id: str
    passed: bool
    quality_score: float
    reasons: list[str]


class DataHealth(BaseModel):
    accounts_path: str
    tickets_path: str
    accounts_exists: bool
    tickets_exists: bool
    accounts_bytes: int
    tickets_bytes: int
    accounts_count: int
    tickets_count: int
    accounts_error: str | None = None
    tickets_error: str | None = None
    ready_for_account_briefs: bool


class LoadedAccount(BaseModel):
    account_id: str
    raw: dict[str, Any]


class LoadedTicket(BaseModel):
    ticket_id: str
    account_id: str
    subject: str
    body: str
    created_at: str | None = None
    status: str
    priority: str
    raw: dict[str, Any]
