from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"\+?1?[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"
)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_LONG_DIGIT_RE = re.compile(r"\b\d{12,}\b")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9]{24,}\b")


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _IPV4_RE.sub("[IP]", text)
    text = _LONG_DIGIT_RE.sub("[ID]", text)
    text = _LONG_TOKEN_RE.sub("[TOKEN]", text)
    return text


def redact_record(value: Any) -> Any:
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        return {k: redact_record(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_record(item) for item in value]
    return value
