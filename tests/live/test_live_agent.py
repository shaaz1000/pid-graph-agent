"""Live checks against the configured hosted model. Excluded by default.

    uv run pytest -m live

Assertions are about behaviour that must hold regardless of wording.
"""

from __future__ import annotations

import pytest

from pid_agent.agent.workflow import PidAgent
from pid_agent.config import load_settings
from pid_agent.llm import create_llm

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def agent(tools):
    settings = load_settings()
    if not settings.llm_api_key:
        pytest.skip("no API key is configured for the selected provider")
    return PidAgent(create_llm(settings), tools)


def used(result):
    return [s.tool for s in result.trace if s.executed]


def test_direct_connection_question(agent):
    result = agent.ask("Which line leaves the centrifugal pump, and how big is it?")
    assert result.grounding_status in ("grounded", "regenerated")
    assert "47122" in result.answer and "80" in result.answer


def test_multi_step_question(agent):
    result = agent.ask("What is the set pressure of the safety valve, and which tank does it relieve to?")
    assert len(used(result)) >= 2
    assert "6.0" in result.answer and "T4750" in result.answer


def test_missing_property_is_an_abstention(agent):
    result = agent.ask("When was tank T4750 last inspected?")
    assert "get_properties" in used(result) or "get_entity" in used(result)
    assert result.unsupported_claims == []
    assert any(word in result.answer.lower() for word in ("not contain", "no ", "not available", "does not", "doesn't"))


def test_unknown_tag_is_not_bound_to_a_similar_one(agent):
    result = agent.ask("What is the shaft power of pump P4717?")
    assert "60.0" not in result.answer and "84.0" not in result.answer
    assert "not" in result.answer.lower()
