"""Explicit configuration, read once from the environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from pid_agent.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "C01V04-VER.EX01.xml"
DEFAULT_LLM_PROVIDER = "groq"
DEFAULT_LLM_MODEL = "openai/gpt-oss-20b"


@dataclass(frozen=True)
class Settings:
    data_file: Path = DEFAULT_DATA_FILE
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: str = DEFAULT_LLM_MODEL
    # repr=False keeps the secret out of logs, tracebacks and debug prints.
    llm_api_key: str | None = field(default=None, repr=False)
    max_traversal_depth: int = 25

    def require_api_key(self) -> str:
        if not self.llm_api_key:
            raise ConfigError(
                "No LLM API key configured. Set GROQ_API_KEY in your environment or .env file."
            )
        return self.llm_api_key


def load_settings(env_file: Path | None = None) -> Settings:
    """Build Settings from the process environment, optionally seeded from a .env file."""
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
    data_file = Path(os.environ.get("PID_DATA_FILE") or DEFAULT_DATA_FILE).expanduser()
    return Settings(
        data_file=data_file,
        llm_provider=os.environ.get("LLM_PROVIDER") or DEFAULT_LLM_PROVIDER,
        llm_model=os.environ.get("LLM_MODEL") or DEFAULT_LLM_MODEL,
        llm_api_key=os.environ.get("GROQ_API_KEY") or None,
    )
