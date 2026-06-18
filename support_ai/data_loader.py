from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from support_ai.deterministic import stable_hash
from support_ai.schemas import DataHealth, LoadedAccount, LoadedTicket

_ACCOUNT_ID_KEYS = ["account_id", "accountid", "id", "customer_id", "customerid", "account", "customer"]
_TICKET_ID_KEYS = ["ticket_id", "ticketid", "id", "case_id", "caseid"]
_SUBJECT_KEYS = ["subject", "title", "summary"]
_BODY_KEYS = ["body", "description", "message", "text", "content"]
_CREATED_KEYS = ["created_at", "createdat", "created_date", "createddate", "timestamp", "date"]
_STATUS_KEYS = ["status", "state"]
_PRIORITY_KEYS = ["priority", "severity", "urgency"]

_CONTAINER_KEYS = {"data", "records", "accounts", "tickets", "items", "results"}

_DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def load_json_file(path: str) -> Tuple[Optional[Any], Optional[str]]:
    if not os.path.exists(path):
        return None, f"file not found: {path}"
    if os.path.getsize(path) == 0:
        return None, "empty file"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"


def coerce_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in _CONTAINER_KEYS:
            if key in payload and isinstance(payload[key], list):
                return [r for r in payload[key] if isinstance(r, dict)]
        if payload and all(isinstance(v, dict) for v in payload.values()):
            records = []
            for outer_key, val in payload.items():
                rec = dict(val)
                rec.setdefault("_outer_key", outer_key)
                records.append(rec)
            return records
        return [payload]
    return []


def extract_first(raw: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    lower_map: Dict[str, Any] = {k.lower(): v for k, v in raw.items()}
    for key in keys:
        val = lower_map.get(key.lower())
        if val is not None and val != "":
            return val
    return default


def parse_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return s


def load_accounts(data_dir: str) -> List[LoadedAccount]:
    path = os.path.join(data_dir, "accounts.json")
    payload, _ = load_json_file(path)
    if payload is None:
        return []
    accounts = []
    for rec in coerce_records(payload):
        raw_id = extract_first(rec, _ACCOUNT_ID_KEYS)
        account_id = str(raw_id) if raw_id is not None else stable_hash(str(rec))[:12]
        accounts.append(LoadedAccount(account_id=account_id, raw=rec))
    return accounts


def load_tickets(data_dir: str) -> List[LoadedTicket]:
    path = os.path.join(data_dir, "tickets.json")
    payload, _ = load_json_file(path)
    if payload is None:
        return []
    tickets = []
    for rec in coerce_records(payload):
        raw_id = extract_first(rec, _TICKET_ID_KEYS)
        ticket_id = str(raw_id) if raw_id is not None else stable_hash(str(rec))[:12]
        raw_acct = extract_first(rec, _ACCOUNT_ID_KEYS)
        account_id = str(raw_acct) if raw_acct is not None else ""
        subject = str(extract_first(rec, _SUBJECT_KEYS) or "")
        body = str(extract_first(rec, _BODY_KEYS) or "")
        created_at = parse_datetime(extract_first(rec, _CREATED_KEYS))
        status = str(extract_first(rec, _STATUS_KEYS) or "")
        priority = str(extract_first(rec, _PRIORITY_KEYS) or "")
        tickets.append(LoadedTicket(
            ticket_id=ticket_id,
            account_id=account_id,
            subject=subject,
            body=body,
            created_at=created_at,
            status=status,
            priority=priority,
            raw=rec,
        ))
    return tickets


def get_account_by_id(data_dir: str, account_id: str) -> Optional[LoadedAccount]:
    for acc in load_accounts(data_dir):
        if acc.account_id == account_id:
            return acc
    return None


def get_tickets_for_account(data_dir: str, account_id: str) -> List[LoadedTicket]:
    return [t for t in load_tickets(data_dir) if t.account_id == account_id]


def dataset_health(data_dir: str) -> DataHealth:
    acc_path = os.path.join(data_dir, "accounts.json")
    tkt_path = os.path.join(data_dir, "tickets.json")

    acc_exists = os.path.exists(acc_path)
    tkt_exists = os.path.exists(tkt_path)
    acc_bytes = os.path.getsize(acc_path) if acc_exists else 0
    tkt_bytes = os.path.getsize(tkt_path) if tkt_exists else 0

    acc_payload, acc_error = load_json_file(acc_path)
    tkt_payload, tkt_error = load_json_file(tkt_path)

    acc_count = len(coerce_records(acc_payload)) if acc_payload is not None else 0
    tkt_count = len(coerce_records(tkt_payload)) if tkt_payload is not None else 0

    return DataHealth(
        accounts_path=acc_path,
        tickets_path=tkt_path,
        accounts_exists=acc_exists,
        tickets_exists=tkt_exists,
        accounts_bytes=acc_bytes,
        tickets_bytes=tkt_bytes,
        accounts_count=acc_count,
        tickets_count=tkt_count,
        accounts_error=acc_error,
        tickets_error=tkt_error,
        ready_for_account_briefs=acc_count > 0 and tkt_error is None,
    )


def ticket_summary_stats(data_dir: str) -> dict:
    """Return high-level aggregate statistics about the ticket dataset.

    Returns a dict with keys:
        total (int): Number of tickets loaded.
        by_priority (dict): Count per priority value.
        categories_seen (list): Placeholder for future category indexing.

    Fails gracefully to zeroed stats when data is absent so callers do not
    need to guard against exceptions — check total > 0 before rendering charts.
    """
    try:
        tickets = load_tickets(data_dir)
    except Exception:
        return {"total": 0, "by_priority": {}, "categories_seen": []}

    by_priority: dict = {}
    for t in tickets:
        p = getattr(t, "priority", "unknown") or "unknown"
        by_priority[p] = by_priority.get(p, 0) + 1

    return {
        "total": len(tickets),
        "by_priority": by_priority,
        "categories_seen": [],
    }
