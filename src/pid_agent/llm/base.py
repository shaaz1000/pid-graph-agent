"""Provider-neutral LLM interface.

Messages use the widely supported chat format (``role`` / ``content`` / ``tool_calls`` /
``tool_call_id``); tools are passed as name + description + JSON-schema parameters. A new
provider only has to implement ``LLMClient.complete``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pid_agent.errors import PidAgentError

ToolChoice = Literal["auto", "required", "none"]
Message = dict[str, Any]


ErrorCategory = Literal[
    "rate_limit",
    "authentication",
    "provider_unavailable",
    "invalid_request",
    "output_parse_failed",
    "unknown_provider_error",
]


class LLMError(PidAgentError):
    """The model could not be called. This is an infrastructure failure: it says nothing
    about the plant, and must never be read as "not found" or as an abstention."""

    def __init__(self, message: str, category: ErrorCategory = "unknown_provider_error") -> None:
        super().__init__(message)
        self.category: ErrorCategory = category


def category_for_status(status: int | None) -> ErrorCategory:
    """Map an HTTP status to an error category (shared by all HTTP-based providers)."""
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "authentication"
    if status in (400, 404, 413, 422):
        return "invalid_request"
    if status is not None and status >= 500:
        return "provider_unavailable"
    return "unknown_provider_error"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] | None
    raw_arguments: str = ""
    parse_error: str | None = None

    @classmethod
    def from_raw(cls, call_id: str, name: str, raw_arguments: str | None) -> ToolCall:
        """Parse the model's argument string; a bad string becomes a recorded parse error."""
        name = clean_tool_name(name)
        raw = raw_arguments or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return cls(call_id, name, None, raw, f"arguments are not valid JSON ({exc.msg})")
        if not isinstance(parsed, dict):
            return cls(call_id, name, None, raw, "arguments must be a JSON object")
        return cls(call_id, name, parsed, raw)


# Some hosted models leak chat-protocol control tokens into the name of a tool call
# ("get_entity<|channel|>commentary"). Such a token starts with this marker.
CONTROL_TOKEN = "<|"


def clean_tool_name(name: str) -> str:
    """The tool name without a trailing protocol control token.

    Only that contamination is removed. The name is not matched against the known tools and
    nothing is guessed: a name that is not a tool is still rejected when it is dispatched.
    """
    return name.split(CONTROL_TOKEN, 1)[0].strip() if CONTROL_TOKEN in (name or "") else name


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Set when the provider rejected the model's output as an unusable tool call.
    malformed_output: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    model: str | None = None
    duration_ms: float = 0.0
    # Why generation ended, as the provider reported it: "stop", "tool_calls", "length", ...
    finish_reason: str | None = None

    @property
    def truncated(self) -> bool:
        """The output hit the token limit and is incomplete. Such text must not be parsed as an answer."""
        return self.finish_reason == "length"


def response_from_chat_completion(payload: Any, duration_ms: float = 0.0) -> LLMResponse:
    """Normalise an OpenAI-style chat-completion body. Raises LLMError if it is not one."""
    try:
        choice = payload["choices"][0]
        message = choice["message"]
        calls = [
            ToolCall.from_raw(str(call.get("id") or f"call_{index}"), call["function"]["name"], call["function"].get("arguments"))
            for index, call in enumerate(message.get("tool_calls") or [])
        ]
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError("The provider returned a response that is not a chat completion.", "output_parse_failed") from exc
    usage = payload.get("usage") or {}
    counts = {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    # Hidden reasoning counts against the output limit; keep the figure when the provider reports it.
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if isinstance(reasoning, int):
        counts["reasoning_tokens"] = reasoning
    return LLMResponse(
        # Only the answer text is kept; any reasoning field is ignored.
        content=message.get("content"),
        tool_calls=calls,
        usage=counts,
        model=payload.get("model"),
        duration_ms=duration_ms,
        finish_reason=choice.get("finish_reason") if isinstance(choice, dict) else None,
    )


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: ToolChoice = "auto",
    ) -> LLMResponse: ...


def assistant_message(response: LLMResponse) -> Message:
    """The assistant turn to append to the conversation after a response."""
    message: Message = {"role": "assistant", "content": response.content or ""}
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.raw_arguments or "{}"},
            }
            for call in response.tool_calls
        ]
    return message
