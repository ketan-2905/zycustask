from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from support_ai.account_brief import (
    AccountDataUnavailable,
    AccountNotFound,
    generate_account_brief,
)
from support_ai.config import load_settings
from support_ai.data_loader import dataset_health
from support_ai.schemas import AccountBrief, DataHealth, TriageOutput
from support_ai.triage import triage_ticket

app = FastAPI(title="Zycus Support AI", version="0.1.0")


class TriageRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    text: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "zycus-support-ai"}


@app.get("/data-health", response_model=DataHealth)
def data_health() -> DataHealth:
    settings = load_settings()
    return dataset_health(settings.data_dir)


@app.post("/triage", response_model=TriageOutput)
def triage(req: TriageRequest) -> TriageOutput:
    settings = load_settings()
    if req.text:
        ticket_input: object = {"text": req.text, "subject": req.text[:200], "body": req.text}
    else:
        ticket_input = {"subject": req.subject or "", "body": req.body or ""}
    return triage_ticket(ticket_input, kb_dir=settings.kb_dir, settings=settings)


@app.get("/accounts/{account_id}/brief", response_model=AccountBrief)
def account_brief(account_id: str) -> AccountBrief:
    settings = load_settings()
    try:
        return generate_account_brief(account_id, data_dir=settings.data_dir, settings=settings)
    except AccountDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AccountNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/kb-health")
def kb_health() -> dict:
    """Return the count of knowledge-base documents currently loaded.

    Useful in Kubernetes readiness probes that need granular service health
    beyond the basic /health check.
    """
    from support_ai.kb_retrieval import kb_doc_count
    settings = load_settings()
    count = kb_doc_count(settings.kb_dir)
    return {
        "kb_dir": settings.kb_dir,
        "document_count": count,
        "status": "ok" if count > 0 else "empty",
    }
