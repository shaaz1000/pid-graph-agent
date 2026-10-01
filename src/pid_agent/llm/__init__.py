"""LLM providers. The agent depends only on ``LLMClient``."""

from __future__ import annotations

from pid_agent.config import Settings
from pid_agent.errors import ConfigError
from pid_agent.llm.base import LLMClient


def create_llm(settings: Settings) -> LLMClient:
    """Build the one provider named by LLM_PROVIDER. Add new providers here.

    Selection is explicit: a failing provider is reported, never silently replaced by another,
    so every run is attributable to a single provider and model.
    """
    provider = settings.llm_provider.lower()
    if provider == "groq":
        from pid_agent.llm.groq_provider import GroqProvider

        return GroqProvider(api_key=settings.require_api_key(), model=settings.llm_model)
    if provider in ("nvidia", "openrouter", "deepseek"):
        from pid_agent.llm.deepseek_provider import DeepSeekProvider
        from pid_agent.llm.nvidia_provider import NvidiaProvider
        from pid_agent.llm.openrouter_provider import OpenRouterProvider

        if not settings.llm_model:
            raise ConfigError(
                f"LLM_PROVIDER={provider} needs LLM_MODEL set to the id of a tool-calling model "
                "available from that provider. No default is assumed."
            )
        adapter = {"nvidia": NvidiaProvider, "openrouter": OpenRouterProvider, "deepseek": DeepSeekProvider}[provider]
        return adapter(api_key=settings.require_api_key(), model=settings.llm_model, base_url=settings.llm_base_url)
    raise ConfigError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Supported: groq, nvidia, openrouter, deepseek.")
