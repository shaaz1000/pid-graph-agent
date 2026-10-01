"""DeepSeek's hosted API, used as a development and diagnostic provider.

Selected explicitly with ``LLM_PROVIDER=deepseek`` and ``LLM_MODEL=<model id>``. It is not
the configuration the evaluation is run with (see README / .env.example).
"""

from __future__ import annotations

from pid_agent.llm.openai_compatible import OpenAICompatibleProvider

BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "DeepSeek"
    base_url = BASE_URL
