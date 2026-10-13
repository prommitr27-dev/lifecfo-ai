"""LLM settings from environment variables.

    LIFECFO_LLM_PROVIDER   none (default) | gemini | groq | ollama | custom
    LIFECFO_LLM_MODEL      model name as the provider lists it
    GEMINI_API_KEY         for provider "gemini"
    GROQ_API_KEY           for provider "groq"
    LIFECFO_LLM_BASE_URL   override the endpoint; required for "custom"
    LIFECFO_LLM_API_KEY    for provider "custom"
    LIFECFO_LLM_TIMEOUT    seconds per request (default 60)

The application never changes provider by itself. If the selected provider
fails, the agent falls back to the deterministic no-LLM mode, which is free.
"custom" exists for a future paid or self-hosted endpoint and is only ever
used when a person selects it explicitly.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from lifecfo.domain.models import Frozen


class ProviderPreset(Frozen):
    label: str
    base_url: str | None
    api_key_env: str | None
    free: bool
    local: bool


PROVIDERS: dict[str, ProviderPreset] = {
    "none": ProviderPreset(label="Offline (no LLM)", base_url=None, api_key_env=None,
                           free=True, local=True),
    "gemini": ProviderPreset(
        label="Google Gemini free tier",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY", free=True, local=False,
    ),
    "groq": ProviderPreset(
        label="GroqCloud free plan", base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY", free=True, local=False,
    ),
    "ollama": ProviderPreset(
        label="Local Ollama model", base_url="http://localhost:11434/v1",
        api_key_env=None, free=True, local=True,
    ),
    "custom": ProviderPreset(
        label="Custom OpenAI-compatible endpoint", base_url=None,
        api_key_env="LIFECFO_LLM_API_KEY", free=False, local=False,
    ),
}


class LLMSettings(Frozen):
    provider: str = "none"
    model: str = ""
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2
    problem: str | None = None  # why the configuration cannot be used, if so

    @property
    def preset(self) -> ProviderPreset:
        return PROVIDERS[self.provider]

    @property
    def uses_llm(self) -> bool:
        return self.provider != "none" and self.problem is None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMSettings":
        env = os.environ if env is None else env
        provider = env.get("LIFECFO_LLM_PROVIDER", "none").strip().lower() or "none"
        if provider not in PROVIDERS:
            return cls(problem=f"Unknown LIFECFO_LLM_PROVIDER '{provider}'. "
                               f"Use one of: {', '.join(PROVIDERS)}.")
        if provider == "none":
            return cls()

        preset = PROVIDERS[provider]
        model = env.get("LIFECFO_LLM_MODEL", "").strip()
        base_url = (env.get("LIFECFO_LLM_BASE_URL", "").strip() or preset.base_url or "")
        api_key = env.get(preset.api_key_env, "").strip() if preset.api_key_env else ""
        try:
            timeout = float(env.get("LIFECFO_LLM_TIMEOUT", "") or 60)
        except ValueError:
            timeout = 60.0

        problem = None
        if not model:
            problem = "LIFECFO_LLM_MODEL is not set."
        elif not base_url:
            problem = "LIFECFO_LLM_BASE_URL is not set."
        elif preset.api_key_env and not api_key and provider != "custom":
            problem = f"{preset.api_key_env} is not set."

        return cls(provider=provider, model=model, base_url=base_url.rstrip("/") or None,
                   api_key=api_key or None, timeout_seconds=timeout, problem=problem)


def load_env_file(path: str | Path = ".env") -> None:
    """Load KEY=VALUE lines into the environment. Existing variables win."""
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))
