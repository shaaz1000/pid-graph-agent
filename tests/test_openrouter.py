"""OpenRouter adapter, exercised entirely against a mock HTTP transport (no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from fakes import ScriptedLLM
from pid_agent.agent.tools import tool_specs
from pid_agent.agent.workflow import PidAgent
from pid_agent.config import Settings, load_settings
from pid_agent.errors import ConfigError
from pid_agent.llm import create_llm
from pid_agent.llm.base import LLMError
from pid_agent.llm.groq_provider import GroqProvider
from pid_agent.llm.openrouter_provider import BASE_URL, OpenRouterProvider

KEY = "dummy-test-credential"
MODEL = "example-org/example-open-model"
MESSAGES = [{"role": "system", "content": "You answer from tools."}, {"role": "user", "content": "hello"}]


def provider_with(handler) -> tuple[OpenRouterProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(record))
    return OpenRouterProvider(api_key=KEY, model=MODEL, http_client=client), seen


def completion(message: dict, usage: dict | None = None) -> httpx.Response:
    return httpx.Response(200, json={"model": MODEL, "choices": [{"message": message}], "usage": usage or {}})


# ------------------------------------------------------------ configuration
def test_provider_is_selected_by_configuration_only():
    assert isinstance(create_llm(Settings(llm_provider="openrouter", llm_model=MODEL, llm_api_key=KEY)), OpenRouterProvider)
    assert isinstance(create_llm(Settings(llm_provider="groq", llm_api_key="k")), GroqProvider)
    assert isinstance(create_llm(Settings(llm_provider="OpenRouter", llm_model=MODEL, llm_api_key=KEY)), OpenRouterProvider)


def test_missing_openrouter_key_names_the_right_variable():
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        create_llm(Settings(llm_provider="openrouter", llm_model=MODEL, llm_api_key=None))


def test_openrouter_model_is_never_assumed():
    with pytest.raises(ConfigError, match="LLM_MODEL"):
        create_llm(Settings(llm_provider="openrouter", llm_model="", llm_api_key=KEY))


def test_each_provider_reads_only_its_own_key(monkeypatch, tmp_path):
    empty = tmp_path / ".env"
    empty.write_text("")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    settings = load_settings(empty)
    assert settings.llm_api_key == "router-key" and settings.llm_model == ""  # no default model

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    settings = load_settings(empty)
    assert settings.llm_api_key == "groq-key" and settings.llm_model == "openai/gpt-oss-20b"


def test_a_missing_key_for_the_selected_provider_is_not_borrowed_from_another(monkeypatch, tmp_path):
    empty = tmp_path / ".env"
    empty.write_text("")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert load_settings(empty).llm_api_key is None


# ------------------------------------------------------- request construction
def test_request_construction_and_tool_schema_forwarding():
    provider, seen = provider_with(lambda request: completion({"content": "hi"}))
    specs = tool_specs()
    provider.complete(MESSAGES, specs, "required")
    (request,) = seen
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions" and request.method == "POST"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["model"] == MODEL and body["messages"] == MESSAGES
    assert body["temperature"] == 0.0 and body["tool_choice"] == "required"
    assert body["tools"] == [{"type": "function", "function": spec} for spec in specs]
    assert KEY not in request.content.decode()


def test_no_tools_means_no_tool_fields():
    provider, seen = provider_with(lambda request: completion({"content": "hi"}))
    provider.complete(MESSAGES)
    body = json.loads(seen[0].content)
    assert "tools" not in body and "tool_choice" not in body


# ------------------------------------------------------------ response parsing
def test_tool_call_parsing():
    message = {"content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "find_entities", "arguments": '{"query": "T4750"}'}},
        {"id": "c2", "type": "function", "function": {"name": "traverse", "arguments": '{"start_entity_id": '}},
    ]}
    provider, _ = provider_with(lambda request: completion(message))
    response = provider.complete(MESSAGES, tool_specs())
    good, bad = response.tool_calls
    assert (good.id, good.name, good.arguments, good.parse_error) == ("c1", "find_entities", {"query": "T4750"}, None)
    assert bad.arguments is None and "not valid JSON" in bad.parse_error  # recorded, not raised
    assert response.content is None


def test_ordinary_text_response_ignores_reasoning_fields():
    provider, _ = provider_with(lambda request: completion({"content": "The tank is T4750.", "reasoning": "private"}))
    response = provider.complete(MESSAGES)
    assert response.content == "The tank is T4750." and response.tool_calls == []
    assert "private" not in repr(response)


def test_token_usage_normalisation():
    provider, _ = provider_with(lambda request: completion({"content": "x"}, {"prompt_tokens": 120, "completion_tokens": 8, "total_tokens": 128, "cost": 0}))
    assert provider.complete(MESSAGES).usage == {"prompt_tokens": 120, "completion_tokens": 8, "total_tokens": 128}
    provider, _ = provider_with(lambda request: completion({"content": "x"}))
    assert provider.complete(MESSAGES).usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


# ------------------------------------------------------------- error handling
@pytest.mark.parametrize(
    ("status", "category"),
    [(429, "rate_limit"), (401, "authentication"), (403, "authentication"), (400, "invalid_request"),
     (404, "invalid_request"), (500, "provider_unavailable"), (503, "provider_unavailable"), (418, "unknown_provider_error")],
)
def test_http_errors_are_normalised(status, category):
    provider, _ = provider_with(lambda request: httpx.Response(status, json={"error": {"message": "nope", "code": status}}))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == category and f"HTTP {status}" in str(raised.value)


def test_rate_limit_reported_inside_a_200_response_is_still_a_rate_limit():
    provider, _ = provider_with(lambda request: httpx.Response(200, json={"error": {"message": "Rate limit exceeded: free-models-per-day", "code": 429}}))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "rate_limit"


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {"tool_calls": [{"id": "x"}]}}]}, ["not", "an", "object"]])
def test_malformed_response_body(payload):
    provider, _ = provider_with(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "output_parse_failed"


def test_non_json_response():
    provider, _ = provider_with(lambda request: httpx.Response(200, text="<html>gateway</html>"))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "output_parse_failed"
    provider, _ = provider_with(lambda request: httpx.Response(502, text="<html>bad gateway</html>"))
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "provider_unavailable"


def test_network_failure_is_provider_unavailable():
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    provider, _ = provider_with(refuse)
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "provider_unavailable"


def test_no_secret_leaks_into_errors_or_repr():
    echo = lambda request: httpx.Response(401, json={"error": {"message": f"Invalid key {KEY} supplied", "code": 401}})  # noqa: E731
    provider, _ = provider_with(echo)
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert KEY not in str(raised.value) and "<redacted>" in str(raised.value)
    assert KEY not in repr(Settings(llm_provider="openrouter", llm_model=MODEL, llm_api_key=KEY))
    assert len(str(raised.value)) < 300


# ---------------------------------------------- the workflow is provider-agnostic
def test_agent_runs_unchanged_on_the_openrouter_adapter(tools):
    turns = iter([
        completion({"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "find_entities", "arguments": '{"query": "T4750"}'}}]}, {"prompt_tokens": 900, "completion_tokens": 20, "total_tokens": 920}),
        completion({"content": 'T4750 is Tank-1.\n\n```claims\n[{"predicate": "identified_as", "subject": "Tank-1", "value": "T4750"}]\n```'}, {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010}),
    ])
    provider, seen = provider_with(lambda request: next(turns))
    result = PidAgent(provider, tools).ask("Which entity is T4750?")
    assert result.answer == "T4750 is Tank-1." and result.grounding_status == "grounded"
    assert [s.tool for s in result.trace] == ["find_entities"]
    assert result.usage == {"llm_calls": 2, "prompt_tokens": 1900, "completion_tokens": 30, "total_tokens": 1930}
    second = json.loads(seen[1].content)["messages"]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "tool"]
    assert second[2]["tool_calls"][0]["id"] == second[3]["tool_call_id"] == "c1"


def test_rate_limit_ends_the_run_without_switching_provider(tools):
    """No failover: the configured provider is the only one ever called."""
    provider, seen = provider_with(lambda request: httpx.Response(429, json={"error": {"message": "daily limit", "code": 429}}))
    result = PidAgent(provider, tools).ask("What does T4750 feed?")
    assert len(seen) == 1 and all(request.url.host == "openrouter.ai" for request in seen)
    assert result.failure_category == "rate_limit" and result.grounding_status == "fallback"
    assert "infrastructure failure" in result.answer


def test_scripted_and_real_adapters_satisfy_the_same_interface():
    for client in (ScriptedLLM("x"), OpenRouterProvider(api_key=KEY, model=MODEL), GroqProvider(api_key="k", model="m")):
        assert callable(getattr(client, "complete"))
