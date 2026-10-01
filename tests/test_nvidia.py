"""NVIDIA adapter boundary, against a mock HTTP transport (no network)."""

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
from pid_agent.llm.nvidia_provider import BASE_URL, NvidiaProvider

KEY = "dummy-test-credential"
MODEL = "example-model-id"
MESSAGES = [{"role": "system", "content": "You answer from tools."}, {"role": "user", "content": "hello"}]


def provider_with(handler) -> tuple[NvidiaProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(record))
    return NvidiaProvider(api_key=KEY, model=MODEL, http_client=client), seen


def completion(message: dict, usage: dict | None = None) -> httpx.Response:
    return httpx.Response(200, json={"model": MODEL, "choices": [{"message": message}], "usage": usage or {}})


def test_selected_only_by_explicit_configuration(monkeypatch, tmp_path):
    assert isinstance(create_llm(Settings(llm_provider="nvidia", llm_model=MODEL, llm_api_key=KEY)), NvidiaProvider)
    empty = tmp_path / ".env"
    empty.write_text("")
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    settings = load_settings(empty)
    assert settings.llm_api_key == "nvidia-key"  # its own key, never another provider's
    assert settings.llm_model == ""  # no model is assumed


def test_missing_key_and_missing_model_are_clear_errors():
    with pytest.raises(ConfigError, match="NVIDIA_API_KEY"):
        create_llm(Settings(llm_provider="nvidia", llm_model=MODEL, llm_api_key=None))
    with pytest.raises(ConfigError, match="LLM_MODEL"):
        create_llm(Settings(llm_provider="nvidia", llm_model="", llm_api_key=KEY))


def test_request_carries_model_messages_and_tool_definitions():
    provider, seen = provider_with(lambda request: completion({"content": "hi"}))
    specs = tool_specs()
    provider.complete(MESSAGES, specs, "required")
    (request,) = seen
    assert str(request.url) == "https://integrate.api.nvidia.com/v1/chat/completions"
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
    assert str(raised.value).startswith(f"NVIDIA API call failed (HTTP {status})")
    assert KEY not in str(raised.value) and "<redacted>" in str(raised.value)


def test_failure_ends_the_run_without_calling_another_provider(tools):
    provider, seen = provider_with(lambda request: httpx.Response(429, json={"error": {"message": "rate limit"}}))
    result = PidAgent(provider, tools).ask("What does T4750 feed?")
    assert len(seen) == 1 and seen[0].url.host == "integrate.api.nvidia.com"
    assert result.failure_category == "rate_limit" and "infrastructure failure" in result.answer


def test_endpoint_is_central_and_can_be_overridden(monkeypatch, tmp_path):
    assert BASE_URL == "https://integrate.api.nvidia.com/v1"
    assert str(create_llm(Settings(llm_provider="nvidia", llm_model=MODEL, llm_api_key=KEY))._http.base_url).rstrip("/") == BASE_URL
    custom = create_llm(Settings(llm_provider="nvidia", llm_model=MODEL, llm_api_key=KEY, llm_base_url="http://localhost:8000/v1"))
    assert str(custom._http.base_url).rstrip("/") == "http://localhost:8000/v1"
    empty = tmp_path / ".env"
    empty.write_text("")
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8000/v1")
    assert load_settings(empty).llm_base_url == "http://localhost:8000/v1"


def test_the_key_never_appears_in_settings_repr_or_error_text():
    settings = Settings(llm_provider="nvidia", llm_model=MODEL, llm_api_key=KEY)
    assert KEY not in repr(settings)
    with pytest.raises(ConfigError) as raised:
        create_llm(Settings(llm_provider="nvidia", llm_model=MODEL, llm_api_key=None))
    assert "NVIDIA_API_KEY" in str(raised.value) and "environment or .env" in str(raised.value)


def test_timeout_is_reported_as_provider_unavailable():
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    provider, _ = provider_with(slow)
    with pytest.raises(LLMError) as raised:
        provider.complete(MESSAGES)
    assert raised.value.category == "provider_unavailable" and KEY not in str(raised.value)


def test_invalid_tool_name_and_arguments_from_the_model_are_refused_not_executed(tools):
    def tool_call(name, arguments):
        return {"id": f"c-{name}", "type": "function", "function": {"name": name, "arguments": arguments}}

    final = 'T4750 is Tank-1.\n\n```claims\n[{"predicate": "identified_as", "subject": "Tank-1", "value": "T4750"}]\n```'
    turns = iter([
        completion({"content": None, "tool_calls": [
            tool_call("run_python", '{"code": "import os"}'),
            tool_call("find_entities", '{"wrong_field": 1}'),
            tool_call("find_entities", '{"query": '),
            tool_call("find_entities", '{"query": "T4750"}'),
        ]}),
        completion({"content": final}),
    ])
    provider, _ = provider_with(lambda request: next(turns))
    result = PidAgent(provider, tools).ask("Which entity is T4750?")
    statuses = [(s.tool, s.status, s.executed) for s in result.trace]
    assert statuses[0][:2] == ("run_python", "error") and "Unknown tool" in result.trace[0].result["message"]
    assert statuses[1][:2] == ("find_entities", "error") and "Invalid arguments" in result.trace[1].result["message"]
    assert statuses[2] == ("find_entities", "error", False)  # malformed JSON arguments
    assert statuses[3] == ("find_entities", "success", True)
    assert result.answer == "T4750 is Tank-1." and result.grounding_level == "grounded"
