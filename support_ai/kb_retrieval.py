from __future__ import annotations

import os
from pathlib import Path
from typing import List

from support_ai.deterministic import clip_text, stable_hash, tokenize
from support_ai.redaction import redact_pii
from support_ai.schemas import KnowledgeDoc, RetrievalMatch

_TITLE_WEIGHT = 3
_PATH_WEIGHT = 2
_CATEGORY_WEIGHT = 1
_CONTENT_WEIGHT = 1
_TOTAL_WEIGHT = _TITLE_WEIGHT + _PATH_WEIGHT + _CATEGORY_WEIGHT + _CONTENT_WEIGHT


def build_doc_id(path: str, kb_dir: str) -> str:
    rel = os.path.relpath(path, kb_dir)
    return stable_hash(rel)[:16]


def extract_title(content: str, path: str) -> str:
    h2: str | None = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return stripped[2:].strip()
        if h2 is None and stripped.startswith("## "):
            h2 = stripped[3:].strip()
    return h2 or Path(path).stem


def extract_category(path: str, kb_dir: str) -> str:
    rel = os.path.relpath(path, kb_dir)
    parts = Path(rel).parts
    return parts[0] if len(parts) > 1 else "general"


def lexical_score(query: str, doc: KnowledgeDoc) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    title_hits = len(query_tokens & set(tokenize(doc.title)))
    path_hits = len(query_tokens & set(tokenize(doc.path)))
    cat_hits = len(query_tokens & set(tokenize(doc.category)))
    content_hits = len(query_tokens & set(tokenize(doc.content)))
    hits = (
        _TITLE_WEIGHT * title_hits
        + _PATH_WEIGHT * path_hits
        + _CATEGORY_WEIGHT * cat_hits
        + _CONTENT_WEIGHT * content_hits
    )
    max_hits = len(query_tokens) * _TOTAL_WEIGHT
    return hits / max_hits


def make_snippet(content: str, query: str, max_chars: int = 500) -> str:
    query_tokens = set(tokenize(query))
    lines = content.splitlines()
    scored: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        hits = len(query_tokens & set(tokenize(stripped)))
        if hits > 0:
            scored.append((hits, i, stripped))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if scored:
        snippet = " … ".join(s for _, _, s in scored[:5])
    else:
        snippet = content.strip()
    return redact_pii(clip_text(snippet, max_chars))


def load_knowledge_docs(kb_dir: str) -> List[KnowledgeDoc]:
    if not os.path.isdir(kb_dir):
        return []
    docs: List[KnowledgeDoc] = []
    for root, _dirs, files in os.walk(kb_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue
            if not content.strip():
                continue
            docs.append(KnowledgeDoc(
                doc_id=build_doc_id(fpath, kb_dir),
                path=fpath,
                title=extract_title(content, fpath),
                category=extract_category(fpath, kb_dir),
                content=content,
            ))
    return docs


def retrieve_docs(
    query: str,
    docs: List[KnowledgeDoc],
    top_k: int = 3,
    min_score: float = 0.05,
) -> List[RetrievalMatch]:
    scored: list[tuple[float, str, RetrievalMatch]] = []
    for doc in docs:
        score = lexical_score(query, doc)
        if score < min_score:
            continue
        scored.append((score, doc.doc_id, RetrievalMatch(
            doc_id=doc.doc_id,
            path=doc.path,
            title=doc.title,
            score=score,
            snippet=make_snippet(doc.content, query),
        )))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [match for _, _, match in scored[:top_k]]


def kb_doc_count(kb_dir: str) -> int:
    """Return the number of knowledge-base documents found in *kb_dir*.

    Returns 0 if the directory is missing or empty rather than raising.
    Used by /kb-health to report KB coverage without loading all content.
    """
    try:
        docs = load_knowledge_docs(kb_dir)
        return len(docs)
    except Exception:
        return 0
