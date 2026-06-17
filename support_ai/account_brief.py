from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from support_ai.config import Settings, load_settings
from support_ai.data_loader import (
    dataset_health,
    get_account_by_id,
    get_tickets_for_account,
    load_tickets,
)
from support_ai.deterministic import clip_text, normalise_text
from support_ai.redaction import redact_pii
from support_ai.schemas import AccountBrief, LoadedAccount, LoadedTicket


class AccountDataUnavailable(RuntimeError):
    pass


class AccountNotFound(RuntimeError):
    pass


_RISK_GROUPS: Dict[str, List[str]] = {
    "churn_risk": [
        "churn", "cancel", "cancellation", "terminate", "competitor",
        "renewal at risk", "not renewing",
    ],
    "escalation": [
        "escalate", "executive", "legal", "complaint", "frustrated",
        "unacceptable", "urgent", "blocker",
    ],
    "reliability": [
        "outage", "down", "unavailable", "data loss", "repeated failure",
        "timeout", "severe latency",
    ],
    "security": [
        "breach", "unauthorized", "exposed", "leaked", "vulnerability",
        "compromised",
    ],
    "business_impact": [
        "qbr", "renewal", "go-live", "production", "revenue", "month-end", "board",
    ],
}

_SEVERITY_MAP: Dict[str, str] = {
    "security": "CRITICAL",
    "churn_risk": "HIGH",
    "reliability": "HIGH",
    "escalation": "MEDIUM",
    "business_impact": "MEDIUM",
}

_ACCOUNT_NAME_KEYS = [
    "name", "company", "account_name", "account", "company_name", "client", "org",
]
_TIER_KEYS = ["tier", "plan", "segment", "level"]
_HEALTH_KEYS = ["health_score", "health", "health_status"]
_OWNER_KEYS = ["owner", "tam", "csm", "account_owner", "account_manager"]


def _extract_field(raw: Dict[str, Any], keys: List[str]) -> Optional[str]:
    lower_map = {k.lower(): v for k, v in raw.items()}
    for key in keys:
        val = lower_map.get(key.lower())
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _parse_ticket_date(ticket: LoadedTicket) -> Optional[datetime]:
    if not ticket.created_at:
        return None
    try:
        dt = datetime.fromisoformat(ticket.created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _max_date(tickets: List[LoadedTicket]) -> Optional[datetime]:
    dates = [_parse_ticket_date(t) for t in tickets]
    valid = [d for d in dates if d is not None]
    return max(valid) if valid else None


def compute_as_of(
    tickets: List[LoadedTicket],
    explicit_as_of: Optional[datetime] = None,
) -> datetime:
    if explicit_as_of is not None:
        return explicit_as_of
    max_date = _max_date(tickets)
    return max_date if max_date is not None else datetime.now(tz=timezone.utc)


def filter_last_90_days(
    tickets: List[LoadedTicket],
    as_of: datetime,
) -> List[LoadedTicket]:
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    cutoff = as_of - timedelta(days=90)
    result = []
    for t in tickets:
        dt = _parse_ticket_date(t)
        if dt is None:
            result.append(t)  # undated tickets are always included
        elif dt >= cutoff:
            result.append(t)
    return result


def extract_direct_quote(
    ticket: LoadedTicket,
    keyword: Optional[str] = None,
    max_chars: int = 220,
) -> str:
    raw_text = f"{ticket.subject} {ticket.body}".strip()
    if not raw_text:
        return ""
    # Redact PII before splitting so email dots don't confuse sentence boundaries
    text = redact_pii(raw_text)
    if keyword:
        norm_kw = normalise_text(keyword)
        for segment in re.split(r"[!?\n]+", text):
            segment = segment.strip()
            if segment and norm_kw in normalise_text(segment):
                return clip_text(segment, max_chars)
    return clip_text(text, max_chars)


def detect_risk_flags(tickets: List[LoadedTicket]) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []
    for ticket in tickets:
        text = normalise_text(f"{ticket.subject} {ticket.body}")
        for risk_type, signals in _RISK_GROUPS.items():
            matched = []
            for sig in signals:
                pattern = r"\b" + re.escape(normalise_text(sig)) + r"\b"
                if re.search(pattern, text):
                    matched.append(sig)
            if matched:
                quote = extract_direct_quote(ticket, keyword=matched[0])
                severity = _SEVERITY_MAP.get(risk_type, "MEDIUM")
                date_note = "" if ticket.created_at else " (ticket date unknown)"
                flags.append({
                    "ticket_id": ticket.ticket_id,
                    "risk_type": risk_type,
                    "severity": severity,
                    "quote": quote,
                    "justification": f"Matched signals: {', '.join(matched)}{date_note}",
                })
    return flags


def _account_meta(account: LoadedAccount) -> Dict[str, Optional[str]]:
    raw = account.raw
    return {
        "name": _extract_field(raw, _ACCOUNT_NAME_KEYS),
        "tier": _extract_field(raw, _TIER_KEYS),
        "health": _extract_field(raw, _HEALTH_KEYS),
        "owner": _extract_field(raw, _OWNER_KEYS),
    }


def build_executive_summary(
    account: LoadedAccount,
    tickets_90d: List[LoadedTicket],
    flags: List[Dict[str, str]],
) -> str:
    meta = _account_meta(account)
    name = meta["name"] or f"Account {account.account_id}"
    tier_str = f" ({meta['tier']} tier)" if meta["tier"] else ""
    health_str = f" Health score: {meta['health']}." if meta["health"] else ""

    sentences = []
    sentences.append(f"{name}{tier_str} is the account under review.{health_str}")

    n = len(tickets_90d)
    if n == 0:
        sentences.append("No tickets were opened in the last 90 days.")
    else:
        open_count = sum(
            1 for t in tickets_90d
            if t.status.lower() in ("open", "new", "pending", "in progress")
        )
        suffix = f", of which {open_count} remain open." if open_count else "."
        sentences.append(f"In the last 90 days, {n} ticket(s) were submitted{suffix}")

    if flags:
        risk_types = list(dict.fromkeys(f["risk_type"] for f in flags))
        sentences.append(
            f"Risk signals detected: {', '.join(risk_types)} across {len(flags)} flagged ticket(s)."
        )
    else:
        sentences.append("No risk signals were detected in recent tickets.")

    if meta["owner"]:
        sentences.append(f"Account owner / TAM: {meta['owner']}.")
    else:
        sentences.append("Account metadata is limited; owner information is unavailable.")

    return " ".join(sentences)


def build_talking_points(
    account: LoadedAccount,
    tickets_90d: List[LoadedTicket],
    flags: List[Dict[str, str]],
) -> List[str]:
    meta = _account_meta(account)
    name = meta["name"] or f"Account {account.account_id}"
    points: List[str] = []

    if not tickets_90d:
        points.append(
            f"Schedule a proactive check-in with {name} — no recent ticket activity."
        )
        points.append("Confirm product adoption and usage trends are on track.")
        points.append("Clarify upcoming renewal, QBR, or go-live milestones.")
        return points

    churn = [f for f in flags if f["risk_type"] == "churn_risk"]
    if churn:
        points.append(
            f"Address churn risk: {len(churn)} ticket(s) signal cancellation or"
            " competitor evaluation — prepare a targeted retention response."
        )

    esc = [f for f in flags if f["risk_type"] == "escalation"]
    if esc:
        points.append(
            f"Acknowledge {len(esc)} escalation ticket(s) and confirm executive sponsor is engaged."
        )

    rel = [f for f in flags if f["risk_type"] == "reliability"]
    if rel:
        points.append(
            f"Follow up on {len(rel)} reliability issue(s) — confirm resolution and share RCA if applicable."
        )

    sec = [f for f in flags if f["risk_type"] == "security"]
    if sec:
        points.append(
            f"Escalate {len(sec)} security-related ticket(s) to the security team immediately."
        )

    biz = [f for f in flags if f["risk_type"] == "business_impact"]
    if biz:
        points.append(
            f"Align on business milestones flagged in {len(biz)} ticket(s) (QBR, go-live, renewal)."
        )

    open_tix = [
        t for t in tickets_90d
        if t.status.lower() in ("open", "new", "pending", "in progress")
    ]
    if open_tix:
        points.append(
            f"Review and resolve {len(open_tix)} open ticket(s) before next TAM touchpoint."
        )

    points.append(
        f"Confirm upcoming renewal and QBR dates with {name} to maintain proactive cadence."
    )

    if len(points) < 3:
        points.append("Review SLA compliance and document any product feedback for the roadmap.")

    return points[:6]


def generate_account_brief(
    account_id: str,
    data_dir: Optional[str] = None,
    as_of: Optional[datetime] = None,
    settings: Optional[Settings] = None,
) -> AccountBrief:
    if settings is None:
        settings = load_settings()
    if data_dir is None:
        data_dir = settings.data_dir

    health = dataset_health(data_dir)
    if not health.accounts_exists or health.accounts_count == 0:
        raise AccountDataUnavailable(
            f"accounts.json is missing or empty in {data_dir!r}"
        )

    account = get_account_by_id(data_dir, account_id)
    if account is None:
        raise AccountNotFound(f"Account ID {account_id!r} not found.")

    all_tickets = load_tickets(data_dir)
    account_tickets = get_tickets_for_account(data_dir, account_id)

    # Priority: explicit as_of > max account ticket date > max dataset date > UTC now
    if as_of is not None:
        effective_as_of = as_of
    else:
        effective_as_of = (
            _max_date(account_tickets)
            or _max_date(all_tickets)
            or datetime.now(tz=timezone.utc)
        )

    tickets_90d = filter_last_90_days(account_tickets, effective_as_of)
    flags = detect_risk_flags(tickets_90d)

    summary = build_executive_summary(account, tickets_90d, flags)
    talking_points = build_talking_points(account, tickets_90d, flags)

    flag_strings = [
        f"[{f['risk_type'].upper()} | {f['severity']}] {f['ticket_id']}"
        f" — \"{f['quote']}\" — {f['justification']}"
        for f in flags
    ]

    source_ids = list(dict.fromkeys(t.ticket_id for t in tickets_90d))

    return AccountBrief(
        account_id=account_id,
        executive_summary=summary,
        open_risks_and_flagged_issues=flag_strings,
        recommended_talking_points=talking_points,
        source_ticket_ids=source_ids,
        deterministic=True,
    )
