"""DeepSeek adapter boundary, against a mock HTTP transport (no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from pid_agent.agent.tools import tool_specs
from pid_agent.agent.workflow import PidAgent
from pid_agent.config import Settings, load_settings
from pid_agent.errors import ConfigError
from pid_agent.llm import create_llm
from pid_agent.llm.base import LLMError
from pid_agent.llm.deepseek_provider import BASE_URL, DeepSeekProvider

KEY = "dummy-test-credential"
MODEL = "example-model-id"
MESSAGES = [{"role": "system", "content": "You answer from tools."}, {"role": "user", "content": "hello"}]


def provider_with(handler) -> tuple[DeepSeekProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(record))
    return DeepSeekProvider(api_key=KEY, model=MODEL, http_client=client), seen


def completion(message: dict, usage: dict | None = None) -> httpx.Response:
    return httpx.Response(200, json={"model": MODEL, "choices": [{"message": message}], "usage": usage or {}})


def test_selected_only_by_explicit_configuration(monkeypatch, tmp_path):
    assert isinstance(create_llm(Settings(llm_provider="deepseek", llm_model=MODEL, llm_api_key=KEY)), DeepSeekProvider)
    empty = tmp_path / ".env"
    empty.write_text("")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEP_SEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    settings = load_settings(empty)
    assert settings.llm_api_key == "deepseek-key"  # its own key, never another provider's
    assert settings.llm_model == ""  # no model is assumed


def test_missing_key_and_missing_model_are_clear_errors():
    with pytest.raises(ConfigError, match="DEEP_SEEK_API_KEY"):
        create_llm(Settings(llm_provider="deepseek", llm_model=MODEL, llm_api_key=None))
    with pytest.raises(ConfigError, match="LLM_MODEL"):
        create_llm(Settings(llm_provider="deepseek", llm_model="", llm_api_key=KEY))


def test_request_carries_model_messages_and_tool_definitions():
    provider, seen = provider_with(lambda request: completion({"content": "hi"}))
    specs = tool_specs()
    provider.complete(MESSAGES, specs, "required")
    (request,) = seen
    assert str(request.url) == "https://api.deepseek.com/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert (body["model"], body["messages"], body["tool_choice"]) == (MODEL, MESSAGES, "required")
    assert body["tools"] == [{"type": "function", "function": spec} for spec in specs]
    assert KEY not in request.content.decode()


def test_tool_calls_text_and_usage_are_normalised():
    message = {"content": "", "reasoning_content": "private", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "find_entities", "arguments": '{"query": "T4750"}'}},
    ]}
    usage = {"prompt_tokens": 50, "completion_tokens": 7, "total_tokens": 57, "prompt_cache_hit_tokens": 40}
    provider, _ = provider_with(lambda request: completion(message, usage))
    response = provider.complete(MESSAGES, tool_specs())
    assert [(c.id, c.name, c.arguments) for c in response.tool_calls] == [("c1", "find_entities", {"query": "T4750"})]
    assert response.usage == {"prompt_tokens": 50, "completion_tokens": 7, "total_tokens": 57}
    assert "private" not in repr(response)

    provider, _ = provider_with(lambda request: completion({"content": "The tank is T4750."}))
    assert provider.complete(MESSAGES).content == "The tank is T4750."


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": {"tool_calls": [{"id": "x"}]}}]}])
def test_malformed_response(payload):
    provider, _ = provider_with(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "output_parse_failed"


@pytest.mark.parametrize(("status", "category"), [(429, "rate_limit"), (401, "authentication"), (400, "invalid_request"), (503, "provider_unavailable")])
def test_errors_are_normalised_and_never_leak_the_key(status, category):
    provider, _ = provider_with(lambda request: httpx.Response(status, json={"error": {"message": f"rejected for key {KEY}"}}))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == category
    assert str(raised.value).startswith(f"DeepSeek API call failed (HTTP {status})")
    assert KEY not in str(raised.value) and "<redacted>" in str(raised.value)


def test_failure_ends_the_run_without_calling_another_provider(tools):
    provider, seen = provider_with(lambda request: httpx.Response(429, json={"error": {"message": "rate limit"}}))
    result = PidAgent(provider, tools).ask("What does T4750 feed?")
    assert len(seen) == 1 and seen[0].url.host == "api.deepseek.com"
    assert result.failure_category == "rate_limit" and "infrastructure failure" in result.answer
