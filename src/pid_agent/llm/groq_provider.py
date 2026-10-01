"""Groq-hosted open-weight models (default: openai/gpt-oss-20b)."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from pid_agent.llm.base import ErrorCategory, LLMError, LLMResponse, Message, ToolCall, ToolChoice, category_for_status

logger = logging.getLogger(__name__)
MALFORMED_OUTPUT_CODES = {"tool_use_failed", "output_parse_failed"}
# Account identifiers in provider error text are of no use to the reader.
ACCOUNT_DETAIL = re.compile(r"\s*in organization `?org_\w+`?")


class GroqProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        import groq  # imported lazily so the rest of the package works without the SDK

        self._groq = groq
        self._client = groq.Groq(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: ToolChoice = "auto",
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_completion_tokens": self._max_output_tokens,
        }
        if tools:
            request["tools"] = [{"type": "function", "function": tool} for tool in tools]
            request["tool_choice"] = tool_choice
        started = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(**request)
        except self._groq.BadRequestError as exc:
            malformed = self._malformed_tool_output(exc)
            if malformed is None:
                raise LLMError(f"Groq rejected the request: {self._describe(exc)}", "invalid_request") from exc
            duration = (time.perf_counter() - started) * 1000
            logger.warning("llm_malformed_tool_call model=%s duration_ms=%.0f", self._model, duration)
            return LLMResponse(malformed_output=malformed, model=self._model, duration_ms=duration)
        except self._groq.APIError as exc:
            raise LLMError(f"Groq API call failed: {self._describe(exc)}", self._category(exc)) from exc

        duration = (time.perf_counter() - started) * 1000
        message = completion.choices[0].message
        usage = completion.usage
        response = LLMResponse(
            # Only the answer text is kept; the model's private reasoning is never read.
            content=message.content,
            tool_calls=[
                ToolCall.from_raw(call.id, call.function.name, call.function.arguments)
                for call in (message.tool_calls or [])
            ],
            usage={
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            },
            model=completion.model,
            duration_ms=duration,
            finish_reason=getattr(completion.choices[0], "finish_reason", None),
        )
        logger.info(
            "llm_call model=%s duration_ms=%.0f tool_calls=%d total_tokens=%d",
            self._model, duration, len(response.tool_calls), response.usage["total_tokens"],
        )
        return response

    @staticmethod
    def _malformed_tool_output(exc: Exception) -> str | None:
        """Groq answers HTTP 400 when the model's output is not a usable tool call or message
        (codes ``tool_use_failed`` and ``output_parse_failed``). That is a model slip the agent
        can recover from, not an API failure."""
        body = getattr(exc, "body", None)
        error = body.get("error", body) if isinstance(body, dict) else {}
        if isinstance(error, dict) and error.get("code") in MALFORMED_OUTPUT_CODES:
            return str(error.get("failed_generation") or error.get("message") or "invalid tool call")
        return None

    def _category(self, exc: Exception) -> ErrorCategory:
        if isinstance(exc, (self._groq.APIConnectionError, self._groq.APITimeoutError)):
            return "provider_unavailable"
        return category_for_status(getattr(exc, "status_code", None))

    @staticmethod
    def _describe(exc: Exception) -> str:
        """Error text for the user. The SDK never includes the API key in its messages."""
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None)
        error = body.get("error", body) if isinstance(body, dict) else None
        text = error.get("message") if isinstance(error, dict) else None
        text = ACCOUNT_DETAIL.sub("", str(text or getattr(exc, "message", None) or exc))
        return f"{type(exc).__name__}{f' (HTTP {status})' if status else ''}: {text[:200].strip()}"
