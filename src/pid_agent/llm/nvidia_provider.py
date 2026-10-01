"""NVIDIA-hosted inference (build.nvidia.com), through its OpenAI-compatible API.

Selected with ``LLM_PROVIDER=nvidia`` and ``LLM_MODEL=<model id>``; the key is read from
``NVIDIA_API_KEY``. ``LLM_BASE_URL`` overrides the endpoint (for a self-hosted NIM, for example).
"""

from __future__ import annotations

from pid_agent.llm.openai_compatible import OpenAICompatibleProvider

BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaProvider(OpenAICompatibleProvider):
    name = "NVIDIA"
    base_url = BASE_URL
    # Observed live: a call usually returns in 2-30 s, but the hosted endpoint at times takes
    # 90-145 s even for a small request. A timeout is a provider failure; it is unrelated to
    # truncated output. Override with LLM_TIMEOUT_SECONDS.
    timeout_seconds = 240.0
    # Documented by NVIDIA for this model family: low-effort reasoning via the chat template.
    # Used only for calls that write up evidence already collected (rewrites, forced answers);
    # planning and tool selection keep the default reasoning.
    synthesis_options = {"chat_template_kwargs": {"enable_thinking": True, "low_effort": True}}
