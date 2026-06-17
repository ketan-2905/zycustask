from __future__ import annotations

from typing import Any, Dict, List, Optional

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
    known_issue_match: Optional[str] = None
    relevant_docs: List[RetrievalMatch] = []
    recommended_team: str
    draft_response: str
    confidence: float


class AccountBrief(BaseModel):
    account_id: str
    executive_summary: str
    open_risks_and_flagged_issues: List[str]
    recommended_talking_points: List[str]
    source_ticket_ids: List[str]
    deterministic: bool = True


class EvalCaseResult(BaseModel):
    task: str
    case_id: str
    passed: bool
    quality_score: float
    reasons: List[str]


class DataHealth(BaseModel):
    accounts_path: str
    tickets_path: str
    accounts_exists: bool
    tickets_exists: bool
    accounts_bytes: int
    tickets_bytes: int
    accounts_count: int
    tickets_count: int
    accounts_error: Optional[str] = None
    tickets_error: Optional[str] = None
    ready_for_account_briefs: bool


class LoadedAccount(BaseModel):
    account_id: str
    raw: Dict[str, Any]


class LoadedTicket(BaseModel):
    ticket_id: str
    account_id: str
    subject: str
    body: str
    created_at: Optional[str] = None
    status: str
    priority: str
    raw: Dict[str, Any]
