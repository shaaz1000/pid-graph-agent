"""LLM providers. The agent depends only on ``LLMClient``."""

from __future__ import annotations

from pid_agent.config import Settings
from pid_agent.errors import ConfigError
from pid_agent.llm.base import LLMClient


def create_llm(settings: Settings) -> LLMClient:
    """Build the configured provider. Add new providers here."""
    provider = settings.llm_provider.lower()
    if provider == "groq":
        from pid_agent.llm.groq_provider import GroqProvider

        return GroqProvider(api_key=settings.require_api_key(), model=settings.llm_model)
    raise ConfigError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Supported: groq.")
