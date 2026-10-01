"""OpenRouter-hosted models, through its OpenAI-compatible chat-completions endpoint.

An optional alternative to the default provider, selected explicitly with
``LLM_PROVIDER=openrouter`` and ``LLM_MODEL=<model id>``. The model id is configuration:
use an open-weight model that supports tool calling.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from pid_agent.llm.base import (
    ErrorCategory,
    LLMError,
    LLMResponse,
    Message,
    ToolChoice,
    category_for_status,
    response_from_chat_completion,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1"
MAX_ERROR_TEXT = 200


class OpenRouterProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
        timeout_seconds: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        # The client is injectable so tests can run against a mock transport, offline.
        self._http = http_client or httpx.Client(base_url=BASE_URL, timeout=timeout_seconds)

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: ToolChoice = "auto",
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_output_tokens,
        }
        if tools:
            body["tools"] = [{"type": "function", "function": tool} for tool in tools]
            body["tool_choice"] = tool_choice
        started = time.perf_counter()
        try:
            reply = self._http.post("/chat/completions", json=body, headers={"Authorization": f"Bearer {self._api_key}"})
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenRouter could not be reached: {type(exc).__name__}", "provider_unavailable") from exc
        duration = (time.perf_counter() - started) * 1000

        payload = self._json(reply)
        error = payload.get("error") if isinstance(payload, dict) else None
        if reply.status_code >= 400 or error:
            raise self._error(reply.status_code, error)
        response = response_from_chat_completion(payload, duration)
        logger.info(
            "llm_call provider=openrouter model=%s duration_ms=%.0f tool_calls=%d total_tokens=%d",
            self._model, duration, len(response.tool_calls), response.usage["total_tokens"],
        )
        return response

    @staticmethod
    def _json(reply: httpx.Response) -> Any:
        try:
            return reply.json()
        except ValueError as exc:
            if reply.status_code >= 400:
                return {"error": {"message": f"HTTP {reply.status_code}"}}
            raise LLMError("OpenRouter returned a response that is not JSON.", "output_parse_failed") from exc

    def _error(self, status: int, error: Any) -> LLMError:
        """OpenRouter reports failures either as an HTTP status or as an ``error`` object
        inside a 200 response (its ``code`` then carries the upstream status)."""
        details = error if isinstance(error, dict) else {}
        code = details.get("code")
        effective = code if isinstance(code, int) and status < 400 else status
        category: ErrorCategory = category_for_status(effective)
        text = str(details.get("message") or f"HTTP {status}").replace(self._api_key, "<redacted>")
        return LLMError(f"OpenRouter API call failed (HTTP {effective}): {text[:MAX_ERROR_TEXT].strip()}", category)
