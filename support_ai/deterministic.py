from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, List, TypeVar

T = TypeVar("T")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", normalise_text(text))


def dedupe_keep_order(items: Iterable[T]) -> List[T]:
    seen: set = set()
    result: List[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(" ", 1)[0]
    return clipped + "…"


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def sorted_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sorted_dict(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [sorted_dict(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(sorted_dict(value), sort_keys=True, ensure_ascii=False)


def clamp_score(value: Any, default: float = 0.0) -> float:
    v = default
    try:
        v = float(value)
    except (TypeError, ValueError):
        pass
    return round(min(1.0, max(0.0, v)), 3)


def truncate_text(text: str, max_chars: int = 500) -> str:
    """Return *text* truncated to *max_chars*, appending '…' when cut.

    Centralises truncation logic to prevent divergent lengths creeping in
    across draft-response generation and KB snippet display.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"
