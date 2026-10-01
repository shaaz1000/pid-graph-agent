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
