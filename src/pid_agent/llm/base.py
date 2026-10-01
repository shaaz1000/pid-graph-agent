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


class LLMError(PidAgentError):
    """The model could not be called (network, authentication, rate limit, server error)."""


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
        raw = raw_arguments or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return cls(call_id, name, None, raw, f"arguments are not valid JSON ({exc.msg})")
        if not isinstance(parsed, dict):
            return cls(call_id, name, None, raw, "arguments must be a JSON object")
        return cls(call_id, name, parsed, raw)


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Set when the provider rejected the model's output as an unusable tool call.
    malformed_output: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    model: str | None = None
    duration_ms: float = 0.0


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
