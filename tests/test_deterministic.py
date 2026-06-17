"""Unit tests for support_ai.deterministic helpers."""
from support_ai.deterministic import clamp_score, normalise_text, truncate_text


def test_clamp_score_within_range():
    assert clamp_score(0.5) == 0.5


def test_clamp_score_below_zero():
    assert clamp_score(-0.1) == 0.0


def test_clamp_score_above_one():
    assert clamp_score(1.5) == 1.0


def test_normalise_text_lowercases():
    assert normalise_text("Hello WORLD") == "hello world"


def test_normalise_text_strips_whitespace():
    assert normalise_text("  spaces  ") == "spaces"


def test_truncate_text_short_string_unchanged():
    assert truncate_text("hi", 10) == "hi"


def test_truncate_text_long_string_gets_ellipsis():
    result = truncate_text("a" * 600, 500)
    assert result.endswith("…")
    assert len(result) <= 501


def test_truncate_text_exact_boundary():
    text = "b" * 500
    assert truncate_text(text, 500) == text
