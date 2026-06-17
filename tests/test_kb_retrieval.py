from __future__ import annotations

import pytest

from support_ai.kb_retrieval import (
    extract_category,
    extract_title,
    load_knowledge_docs,
    make_snippet,
    retrieve_docs,
)


def _make_kb(tmp_path, structure: dict) -> str:
    """Write nested {relative_path: content} into a KB dir under tmp_path."""
    kb = tmp_path / "knowledge-base"
    kb.mkdir()
    for rel, content in structure.items():
        p = kb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return str(kb)


# 1 — empty KB returns no docs
def test_empty_kb_returns_no_docs(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    assert load_knowledge_docs(str(kb)) == []


def test_absent_kb_returns_no_docs(tmp_path):
    assert load_knowledge_docs(str(tmp_path / "nonexistent")) == []


# 2 — H1 title extraction
def test_h1_title_extracted(tmp_path):
    kb_dir = _make_kb(tmp_path, {"auth/sso.md": "# Single Sign-On\n\nConfigure SSO here.\n"})
    docs = load_knowledge_docs(kb_dir)
    assert len(docs) == 1
    assert docs[0].title == "Single Sign-On"


def test_h2_title_fallback(tmp_path):
    kb_dir = _make_kb(tmp_path, {"auth/sso.md": "## SSO Setup\n\nConfigure SSO.\n"})
    docs = load_knowledge_docs(kb_dir)
    assert docs[0].title == "SSO Setup"


def test_stem_title_fallback(tmp_path):
    kb_dir = _make_kb(tmp_path, {"auth/sso-guide.md": "No heading here.\n"})
    docs = load_knowledge_docs(kb_dir)
    assert docs[0].title == "sso-guide"


# 3 — folder category extraction
def test_folder_category_extracted(tmp_path):
    kb_dir = _make_kb(tmp_path, {
        "authentication/sso.md": "# SSO\n\nSome content.\n",
        "billing/invoices.md": "# Invoices\n\nBilling info.\n",
    })
    docs = {d.title: d for d in load_knowledge_docs(kb_dir)}
    assert docs["SSO"].category == "authentication"
    assert docs["Invoices"].category == "billing"


def test_root_level_doc_gets_general_category(tmp_path):
    kb_dir = _make_kb(tmp_path, {"overview.md": "# Overview\n\nTop-level doc.\n"})
    docs = load_knowledge_docs(kb_dir)
    assert docs[0].category == "general"


# 4 — relevant doc ranks above unrelated doc
def test_relevant_doc_ranks_higher(tmp_path):
    kb_dir = _make_kb(tmp_path, {
        "auth/sso.md": "# SSO Login\n\nSSO authentication login configuration.\n",
        "billing/invoice.md": "# Invoice\n\nBilling payment invoice generation.\n",
    })
    docs = load_knowledge_docs(kb_dir)
    results = retrieve_docs("SSO login issue", docs, top_k=2)
    assert len(results) >= 1
    assert results[0].title == "SSO Login"


# 5 — empty Markdown files are skipped
def test_empty_markdown_skipped(tmp_path):
    kb_dir = _make_kb(tmp_path, {
        "auth/empty.md": "",
        "auth/whitespace.md": "   \n\n  ",
        "auth/real.md": "# Real Doc\n\nHas content.\n",
    })
    docs = load_knowledge_docs(kb_dir)
    titles = [d.title for d in docs]
    assert len(docs) == 1
    assert "Real Doc" in titles


# 6 — snippet is capped at max_chars and PII is redacted
def test_snippet_capped_and_pii_redacted(tmp_path):
    long_content = (
        "# Auth Issues\n\n"
        "Contact admin@secret.com for SSO login problems. "
        + ("SSO login authentication is important. " * 30)
    )
    kb_dir = _make_kb(tmp_path, {"auth/auth.md": long_content})
    docs = load_knowledge_docs(kb_dir)
    snippet = make_snippet(docs[0].content, "SSO login", max_chars=100)
    assert len(snippet) <= 110  # allow for ellipsis character
    assert "admin@secret.com" not in snippet
    assert "[EMAIL]" in snippet
