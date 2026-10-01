"""A scripted stand-in for the hosted model, so agent tests are deterministic and free."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pid_agent.llm.base import LLMResponse, ToolCall

Turn = Any  # str | list[ToolCall] | LLMResponse | Exception | Callable[[list[dict]], Turn]


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=f"call_{name}_{abs(hash(json.dumps(arguments, sort_keys=True, default=str))) % 10**6}", name=name, arguments=arguments, raw_arguments=json.dumps(arguments))


def bad_json_call(name: str, raw: str) -> ToolCall:
    return ToolCall.from_raw("call_bad", name, raw)


class ScriptedLLM:
    """Plays back a fixed list of turns. The last turn repeats if the agent keeps asking."""

    def __init__(self, *turns: Turn) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages, tools=None, tool_choice="auto") -> LLMResponse:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools, "tool_choice": tool_choice})
        turn = self._turns[min(len(self.calls) - 1, len(self._turns) - 1)]
        if callable(turn) and not isinstance(turn, Exception):
            turn = turn(messages)
        if isinstance(turn, Exception):
            raise turn
        if isinstance(turn, LLMResponse):
            response = turn
        elif isinstance(turn, str):
            response = LLMResponse(content=turn)
        else:
            response = LLMResponse(tool_calls=list(turn))
        response.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        return response

    def tool_messages(self) -> list[dict[str, Any]]:
        """Every tool observation the model was shown in the final call."""
        return [json.loads(m["content"]) for m in self.calls[-1]["messages"] if m["role"] == "tool"]
