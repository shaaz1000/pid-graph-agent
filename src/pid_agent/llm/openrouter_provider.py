"""OpenRouter-hosted models.

An optional alternative to the default provider, selected explicitly with
``LLM_PROVIDER=openrouter`` and ``LLM_MODEL=<model id>``. The model id is configuration:
use an open-weight model that supports tool calling.
"""

from __future__ import annotations

from pid_agent.llm.openai_compatible import OpenAICompatibleProvider

BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "OpenRouter"
    base_url = BASE_URL
