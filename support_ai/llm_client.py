from __future__ import annotations

import json

from support_ai.config import Settings
from support_ai.redaction import redact_record


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        return self._settings.llm_provider.lower() not in ("none", "")

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict,
        schema_name: str,
    ) -> dict:
        if not self.enabled():
            raise LLMUnavailable(
                f"LLM provider is '{self._settings.llm_provider}'. "
                "Set LLM_PROVIDER=openai or LLM_PROVIDER=groq in .env to enable LLM features."
            )
        # PII is redacted before the payload leaves the process.
        safe_payload = redact_record(user_payload)
        provider = self._settings.llm_provider.lower()
        if provider == "openai":
            return self._call_openai(system_prompt, safe_payload, schema_name)
        if provider == "groq":
            return self._call_groq(system_prompt, safe_payload, schema_name)
        raise LLMUnavailable(
            f"Provider '{provider}' is not supported. "
            "Supported values: openai, groq."
        )

    def _call_openai(
        self,
        system_prompt: str,
        user_payload: dict,
        schema_name: str,
    ) -> dict:
        try:
            import openai  # type: ignore[import]
        except ImportError as exc:
            raise LLMUnavailable(
                "openai package not installed. Run: pip install openai"
            ) from exc

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=self._settings.llm_model or "gpt-4o-mini",
            temperature=self._settings.llm_temperature,
            seed=self._settings.llm_seed,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def _call_groq(
        self,
        system_prompt: str,
        user_payload: dict,
        schema_name: str,  # noqa: ARG002 — reserved for future structured-output support
    ) -> dict:
        try:
            from groq import Groq  # type: ignore[import]
        except ImportError as exc:
            raise LLMUnavailable(
                "groq package not installed. Run: pip install groq"
            ) from exc

        client = Groq()
        # Groq requires the word "json" in the system prompt when using json_object format.
        effective_prompt = system_prompt if "json" in system_prompt.lower() else system_prompt + " Respond with valid JSON only."
        response = client.chat.completions.create(
            model=self._settings.llm_model or "llama-3.3-70b-versatile",
            temperature=self._settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": effective_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


def is_llm_enabled(settings=None) -> bool:
    """Return True if an active (non-none) LLM provider is configured.

    Centralises the 'is LLM active?' check so every call-site avoids
    re-implementing the provider string comparison.
    """
    from support_ai.config import load_settings as _load
    s = settings or _load()
    return (s.llm_provider or "none").strip().lower() != "none"
