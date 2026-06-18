"""Tests for config loading and helper functions."""
import os
from unittest.mock import patch

from support_ai.config import load_settings, get_effective_llm_provider


def test_default_app_env_is_development():
    with patch.dict(os.environ, {}, clear=True):
        s = load_settings()
    assert s.app_env == "development"


def test_default_llm_provider_is_none():
    with patch.dict(os.environ, {}, clear=True):
        s = load_settings()
    assert s.llm_provider == "none"


def test_get_effective_llm_provider_unknown_falls_back_to_none():
    with patch.dict(os.environ, {"LLM_PROVIDER": "mistral"}, clear=False):
        s = load_settings()
    assert get_effective_llm_provider(s) == "none"


def test_get_effective_llm_provider_openai_accepted():
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
        s = load_settings()
    assert get_effective_llm_provider(s) == "openai"


def test_get_effective_llm_provider_empty_string_falls_back():
    with patch.dict(os.environ, {"LLM_PROVIDER": ""}, clear=False):
        s = load_settings()
    assert get_effective_llm_provider(s) == "none"
