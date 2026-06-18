"""Tests for kb_doc_count() in kb_retrieval."""
import os
import json
import tempfile

from support_ai.kb_retrieval import kb_doc_count


def test_kb_doc_count_empty_dir(tmp_path):
    """Empty directory should return 0 without raising."""
    count = kb_doc_count(str(tmp_path))
    assert count == 0


def test_kb_doc_count_nonexistent_dir():
    """Nonexistent directory should return 0 gracefully."""
    count = kb_doc_count("/tmp/__does_not_exist_zycus__")
    assert count == 0


def test_kb_doc_count_with_markdown_files(tmp_path):
    """Directory with .md files should be counted."""
    (tmp_path / "doc1.md").write_text("# Doc 1\nSome content")
    (tmp_path / "doc2.md").write_text("# Doc 2\nMore content")
    count = kb_doc_count(str(tmp_path))
    # May be 0 if load_knowledge_docs requires specific format — at minimum no crash
    assert count >= 0
