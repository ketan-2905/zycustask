from __future__ import annotations

import pytest

from support_ai.config import Settings
from support_ai.deterministic import clamp_score, stable_json
from support_ai.llm_client import LLMClient, LLMUnavailable


def _none_settings() -> Settings:
    """Return a Settings object with LLM disabled, regardless of .env."""
    return Settings(
        app_env="test",
        data_dir="data",
        kb_dir="knowledge-base",
        reports_dir="reports",
        llm_provider="none",
        llm_model="",
        llm_temperature=0.0,
        llm_seed=42,
    )


# 1 — provider 'none' disables LLM
def test_default_provider_is_none():
    settings = _none_settings()
    assert settings.llm_provider == "none"


# 2 — LLMClient.enabled() is False for none provider
def test_client_disabled_for_none_provider():
    client = LLMClient(_none_settings())
    assert client.enabled() is False


# 3 — generate_json raises LLMUnavailable when disabled
def test_generate_json_raises_llm_unavailable():
    client = LLMClient(_none_settings())
    with pytest.raises(LLMUnavailable):
        client.generate_json("You are helpful.", {"text": "help"}, "TriageOutput")


# 4 — stable_json is deterministic and sorts keys
def test_stable_json_deterministic():
    data = {"z": 3, "a": 1, "m": {"y": 9, "b": 2}}
    r1 = stable_json(data)
    r2 = stable_json(data)
    assert r1 == r2
    assert r1.index('"a"') < r1.index('"m"') < r1.index('"z"')
    assert r1.index('"b"') < r1.index('"y"')


# 5 — clamp_score bounds and rounds to 3 decimals
def test_clamp_score_bounds_and_rounds():
    assert clamp_score(0.5) == 0.5
    assert clamp_score(1.5) == 1.0
    assert clamp_score(-0.5) == 0.0
    assert clamp_score(0.1234) == 0.123
    assert clamp_score(0.9999) == 1.0
    assert clamp_score("bad") == 0.0
    assert clamp_score(None) == 0.0
