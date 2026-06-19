from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    app_env: str
    data_dir: str
    kb_dir: str
    reports_dir: str
    llm_provider: str
    llm_model: str
    llm_temperature: float
    llm_seed: int


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        data_dir=os.getenv("DATA_DIR", "data"),
        kb_dir=os.getenv("KB_DIR", "knowledge-base"),
        reports_dir=os.getenv("REPORTS_DIR", "reports"),
        llm_provider=os.getenv("LLM_PROVIDER", "none"),
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        llm_seed=int(os.getenv("LLM_SEED", "42")),
    )


def get_effective_llm_provider(settings: Settings) -> str:
    """Return the resolved LLM provider, normalising to 'none' for unknown values.

    Accepted values: 'none', 'openai', 'anthropic'.
    Any other value (empty string, typo, etc.) is treated as 'none' to
    prevent silent mis-configuration that would result in un-authenticated
    API calls at runtime.
    """
    provider = (settings.llm_provider or "none").strip().lower()
    return provider if provider in {"none", "openai", "anthropic"} else "none"
