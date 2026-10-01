"""Provider abstraction: parsing, configuration and error mapping (no network)."""

from __future__ import annotations

import pytest

from pid_agent.config import Settings
from pid_agent.errors import ConfigError
from pid_agent.llm import create_llm
from pid_agent.llm.base import LLMError, LLMResponse, ToolCall, assistant_message
from pid_agent.llm.groq_provider import GroqProvider


def test_tool_call_parsing():
    assert ToolCall.from_raw("1", "t", '{"a": 1}').arguments == {"a": 1}
    assert ToolCall.from_raw("1", "t", None).arguments == {}
    assert "not valid JSON" in ToolCall.from_raw("1", "t", '{"a": ').parse_error
    assert "must be a JSON object" in ToolCall.from_raw("1", "t", "[1, 2]").parse_error


def test_assistant_message_round_trip():
    response = LLMResponse(tool_calls=[ToolCall.from_raw("c1", "find_entities", '{"query": "x"}')])
    message = assistant_message(response)
    assert message["tool_calls"][0] == {"id": "c1", "type": "function", "function": {"name": "find_entities", "arguments": '{"query": "x"}'}}
    assert assistant_message(LLMResponse(content="hi")) == {"role": "assistant", "content": "hi"}


def test_missing_api_key_is_a_clear_config_error():
    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        create_llm(Settings(llm_api_key=None))


def test_unsupported_provider():
    with pytest.raises(ConfigError, match="Unsupported LLM_PROVIDER"):
        create_llm(Settings(llm_provider="somecloud", llm_api_key="k"))


def test_api_key_is_never_in_settings_repr():
    assert "secret-value" not in repr(Settings(llm_api_key="secret-value"))


def test_groq_connection_failure_becomes_llm_error():
    # Nothing listens on this port, so the SDK raises a connection error without leaving the machine.
    provider = GroqProvider(api_key="not-a-real-key", model="m", timeout_seconds=2, max_retries=0)
    provider._client = provider._groq.Groq(api_key="not-a-real-key", base_url="http://127.0.0.1:9", timeout=2, max_retries=0)
    with pytest.raises(LLMError) as raised:
        provider.complete([{"role": "user", "content": "hi"}])
    assert "not-a-real-key" not in str(raised.value)


def test_tool_use_failed_is_reported_as_malformed_output():
    class Rejected(Exception):
        body = {"error": {"code": "tool_use_failed", "failed_generation": "<bad>"}}

    class Unparseable(Exception):
        body = {"error": {"code": "output_parse_failed", "message": "Parsing failed.", "failed_generation": ""}}

    assert GroqProvider._malformed_tool_output(Rejected()) == "<bad>"
    assert GroqProvider._malformed_tool_output(Unparseable()) == "Parsing failed."
    assert GroqProvider._malformed_tool_output(Exception("other")) is None


def test_error_text_is_short_and_drops_account_identifiers():
    class RateLimited(Exception):
        status_code = 429
        body = {"error": {"message": "Rate limit reached for model `m` in organization `org_01abc` service tier `on_demand` on tokens per day (TPD): Limit 200000." + " x" * 300}}

    text = GroqProvider._describe(RateLimited())
    assert text.startswith("RateLimited (HTTP 429): Rate limit reached for model `m` service tier")
    assert "org_" not in text and len(text) < 240
