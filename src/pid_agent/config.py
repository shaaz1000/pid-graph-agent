"""Explicit configuration, read once from the environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from pid_agent.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "C01V04-VER.EX01.xml"
DEFAULT_LLM_PROVIDER = "nvidia"
# The model used when LLM_MODEL is not set. Providers without an entry require LLM_MODEL.
DEFAULT_MODELS = {"nvidia": "nvidia/nemotron-3-super-120b-a12b", "groq": "openai/gpt-oss-20b"}
DEFAULT_LLM_MODEL = DEFAULT_MODELS[DEFAULT_LLM_PROVIDER]
# The environment variable holding the key for each supported provider. Only the key of the
# selected provider is read; there is no fallback from one provider to another.
API_KEY_VARIABLES = {"groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY", "openrouter": "OPENROUTER_API_KEY", "deepseek": "DEEP_SEEK_API_KEY"}


@dataclass(frozen=True)
class Settings:
    data_file: Path = DEFAULT_DATA_FILE
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: str = DEFAULT_LLM_MODEL
    # repr=False keeps the secret out of logs, tracebacks and debug prints.
    llm_api_key: str | None = field(default=None, repr=False)
    # Optional endpoint override for OpenAI-compatible providers; None means the provider's own.
    llm_base_url: str | None = None
    # Seconds allowed for one model call; None means the provider adapter's own default.
    llm_timeout_seconds: float | None = None
    max_traversal_depth: int = 25

    def require_api_key(self) -> str:
        if not self.llm_api_key:
            variable = API_KEY_VARIABLES.get(self.llm_provider.lower(), "the provider's API key")
            raise ConfigError(
                f"No API key configured for LLM_PROVIDER={self.llm_provider}. "
                f"Set {variable} in your environment or .env file."
            )
        return self.llm_api_key


def _positive_number(name: str) -> float | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if value <= 0:
        raise ConfigError(f"{name} must be a positive number of seconds, got '{raw}'.")
    return value


def load_settings(env_file: Path | None = None) -> Settings:
    """Build Settings from the process environment, optionally seeded from a .env file."""
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
    data_file = Path(os.environ.get("PID_DATA_FILE") or DEFAULT_DATA_FILE).expanduser()
    provider = os.environ.get("LLM_PROVIDER") or DEFAULT_LLM_PROVIDER
    key_variable = API_KEY_VARIABLES.get(provider.lower())
    return Settings(
        data_file=data_file,
        llm_provider=provider,
            llm_model=os.environ.get("LLM_MODEL") or DEFAULT_MODELS.get(provider.lower(), ""),
        llm_api_key=(os.environ.get(key_variable) or None) if key_variable else None,
        llm_base_url=os.environ.get("LLM_BASE_URL") or None,
        llm_timeout_seconds=_positive_number("LLM_TIMEOUT_SECONDS"),
    )
