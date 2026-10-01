"""The chat interface's adapter: AgentResult -> display data. No network, no real model."""

from __future__ import annotations

import pytest

from pid_agent.agent.state import AgentResult
from pid_agent.agent.workflow import AgentLimits, PidAgent
from pid_agent.config import PROJECT_ROOT
from pid_agent.llm.base import LLMError
from pid_agent.ui.view_model import EXAMPLE_QUESTIONS, build_view, error_view, graph_facts, summarize_result
from fakes import ScriptedLLM, call


def view_for(tools, question, *turns):
    return build_view(PidAgent(ScriptedLLM(*turns), tools, AgentLimits(claims_retry=False)).ask(question))


def kinds(view):
    return [n.kind for n in view.notices]


def test_successful_answer_keeps_the_agents_text_and_state(tools):
    view = view_for(
        tools, "What is P4711 connected to?",
        [call("find_entities", query="P4711")],
        [call("get_connections", entity_id="CentrifugalPump-1", relationship="piping")],
        "P4711 (CentrifugalPump-1) connects to PlateHeatExchanger-1 (H1007) through line 47122, DN 80.",
    )
    assert view.state == "answered"
    assert view.answer.startswith("P4711 (CentrifugalPump-1) connects to")
    assert view.question == "What is P4711 connected to?"
    assert "3 model calls" in view.usage and "2 tool calls" in view.usage


def test_tool_trace_is_rendered_as_readable_steps_with_raw_result_kept(tools):
    view = view_for(
        tools, "What is P4711 connected to?",
        [call("find_entities", query="P4711")],
        [call("get_connections", entity_id="CentrifugalPump-1", relationship="piping")],
        "P4711 connects to H1007 through line 47122.",
    )
    first, second = view.steps
    assert (first.number, first.tool, first.status, first.executed) == (1, "find_entities", "success", True)
    assert first.inputs == ["query = P4711"]
    assert any("CentrifugalPump-1" in line and "tagName = 'P4711'" in line for line in first.lines)
    assert second.inputs == ["entity_id = CentrifugalPump-1", "relationship = piping"]
    assert any("PlateHeatExchanger-1 (H1007)" in line and "line 47122" in line and "DN 80" in line for line in second.lines)
    assert second.raw["connections"][1]["lineNumber"] == "47122"  # the raw result is still available
    assert view.summary == [
        "1. find_entities(query = P4711) → success",
        "2. get_connections(entity_id = CentrifugalPump-1, relationship = piping) → success",
    ]


def test_evidence_points_back_to_graph_objects(tools):
    view = view_for(tools, "q", [call("get_connections", entity_id="CentrifugalPump-1", relationship="piping")], "Line 47122.")
    connection = next(e for e in view.evidence if e.kind == "connection" and "PipingNetworkSegment-2" in e.id)
    assert connection.source_graph == "conceptual_graph"
    assert connection.source_object_ids and "47122" in connection.fact


def test_grounded_answer_is_reported_without_a_confidence_score(tools):
    final = 'P4711 is CentrifugalPump-1.\n\n```claims\n[{"predicate": "identified_as", "subject": "CentrifugalPump-1", "value": "P4711"}]\n```'
    view = view_for(tools, "q", [call("find_entities", query="P4711")], final)
    g = view.grounding
    assert (g.status, g.level, g.ok, g.label) == ("grounded", "grounded", True, "Grounded: every claim matched graph evidence")
    assert view.answer == "P4711 is CentrifugalPump-1."
    assert not hasattr(view, "confidence") and "confidence" not in g.detail.lower()
    # answer claim -> structured claim -> evidence id -> graph source
    claim = g.claims[0]
    assert claim.text == "identified_as(CentrifugalPump-1, = P4711)"
    fact = claim.facts[0]
    assert fact.evidence_id == "CentrifugalPump-1" and fact.source_graph == "plant_graph" and fact.source_object_ids == ["CentrifugalPump-1"]
    assert "identified_as" in fact.statement and "P4711" in fact.statement


def test_prose_without_claims_is_shown_as_limited_not_grounded(tools):
    view = view_for(tools, "q", [call("find_entities", query="P4711")], "P4711 is CentrifugalPump-1.")
    g = view.grounding
    assert (g.status, g.level, g.ok, g.label) == ("grounded", "limited", False, "Partially grounded (limited)")
    assert g.claims == [] and any("no evidence references" in gap for gap in g.gaps)


def test_result_saved_before_claim_grounding_is_labelled_as_token_level_only():
    old = {"question": "q", "answer": "a", "grounding_status": "grounded", "claims_checked": 14, "trace": [], "evidence": []}
    g = build_view(old).grounding
    assert (g.level, g.label) == ("limited", "Token-level check passed") and "predates structured claims" in g.detail


def test_rejected_draft_then_rewrite_is_visible(tools):
    view = view_for(
        tools, "What power does P4711 need?",
        [call("find_entities", query="P4711")],
        [call("get_properties", ids=["CentrifugalPump-1"], requested_properties=["designShaftPower"])],
        "P4711 needs 75.0 kW.",
        "P4711 has a designShaftPower of 60.0 kW.",
    )
    assert view.grounding.status == "regenerated" and view.grounding.level == "limited"
    assert view.grounding.rejected == ["75.0 kW"] and "rewritten once" in view.grounding.detail
    assert view.state == "answered"


def test_withheld_draft_is_not_presented_as_a_model_answer(tools):
    view = view_for(tools, "What power does P4711 need?", [call("find_entities", query="P4711")], "P4711 needs 75.0 kW.", "P4711 needs 75.0 kW.")
    assert view.state == "withheld"
    assert (view.grounding.ok, view.grounding.level, view.grounding.label) == (False, "insufficient_evidence", "Insufficient evidence: draft withheld")
    assert view.grounding.claims == []
    assert kinds(view)[0] == "withheld"
    assert any("75.0 kW" in claim for claim in view.grounding.unsupported)


def test_ambiguity_lists_the_candidates(tools):
    view = view_for(tools, "Where is valve 73KH12?", [call("find_entities", query="73KH12")], "73KH12 is shared by BallValve-1, BallValve-2, BallValve-3, BallValve-4 and BallValve-5. Which one?")
    assert "ambiguous" in kinds(view)
    assert [c.id for c in view.candidates] == [f"BallValve-{n}" for n in range(1, 6)]
    assert all(c.type == "BallValve" and "73KH12" in c.reason for c in view.candidates)


def test_not_found_is_a_notice_and_suggestions_are_marked_unused(tools):
    view = view_for(tools, "What does P4771 feed?", [call("find_entities", query="P4771")], "P4771 was not found in the P&ID.")
    notice = next(n for n in view.notices if n.kind == "not_found")
    assert notice.title == "Entity not found"
    assert "suggestions only, not used" in notice.detail and "CentrifugalPump-1" in notice.detail
    assert view.state == "answered" and not view.candidates


def test_missing_property_no_path_open_end_truncation_and_boundary_are_distinguished(tools):
    view = view_for(
        tools, "q",
        [
            call("get_properties", ids=["PlateHeatExchanger-1"], requested_properties=["weight"]),
            call("find_path", source_entity_id="Tank-1", target_entity_id="CentrifugalPump-1", direction="downstream"),
            call("get_connections", entity_id="GlobeValve-3", direction="downstream", relationship="piping"),
            call("traverse", start_entity_id="ReciprocatingPump-1", direction="downstream", max_depth=3),
        ],
        "The P&ID does not contain a weight for PlateHeatExchanger-1.",
    )
    found = kinds(view)
    for kind in ("missing_property", "no_path", "open_end", "truncated", "chamber_boundary"):
        assert kind in found, kind
    open_end = next(n for n in view.notices if n.kind == "open_end")
    assert "no destination on this drawing" in open_end.detail and "does not say where it leads" in open_end.detail
    assert view.state == "answered"  # expected graph limitations are not failures


def test_provider_error_is_infrastructure_not_a_graph_statement(tools):
    view = view_for(tools, "What does P4711 feed?", LLMError("Groq API call failed: RateLimitError (HTTP 429)", "rate_limit"))
    assert view.state == "provider_failure"
    assert view.notices[0].kind == "provider_failure" and "rate_limit" in view.notices[0].detail
    assert view.grounding.ok is False and view.grounding.label == "Not validated"
    assert view.steps == []


def test_skipped_duplicate_calls_are_shown_as_not_executed(tools):
    same = [call("find_entities", query="P4711")]
    view = view_for(tools, "q", same, same, "P4711 is CentrifugalPump-1.")
    assert [s.executed for s in view.steps] == [True, False]
    assert view.steps[1].status == "duplicate" and "2 tool calls" not in view.usage


def test_missing_optional_fields_are_tolerated():
    view = build_view({"question": "q", "answer": "a", "trace": [{"tool": "find_entities", "status": "success"}], "evidence": [{"kind": "entity"}]})
    assert view.answer == "a" and view.steps[0].number == 1 and view.steps[0].lines == []
    assert view.evidence[0].id == "?" and view.grounding.status == "not_validated"
    minimal = build_view(AgentResult(question_id="x", question="q", answer="a", trace=[], evidence=[], grounding_status="grounded"))
    assert minimal.steps == [] and minimal.notices == [] and minimal.warnings == []
    assert summarize_result({}) == []


def test_configuration_error_view():
    view = error_view("q", "No API key configured for LLM_PROVIDER=groq.")
    assert view.state == "config_error" and view.notices[0].kind == "config" and view.grounding is None


def test_sidebar_facts_come_from_the_loaded_graph(service, loaded):
    facts = graph_facts(service, loaded)
    assert facts["file"] == "C01V04-VER.EX01.xml"
    assert facts["plant"] == (214, 376) and facts["conceptual"] == (36, 39)
    assert facts["entities"]["equipment"] == 5 and facts["connections"]["open_end"] == 4


def test_example_questions_refer_to_entities_that_exist(tools):
    for tag in ("P4711", "H1007", "HV4750.01"):
        assert tools.call("find_entities", {"query": tag}).status == "success"
    assert len(EXAMPLE_QUESTIONS) == 6


def test_app_renders_and_answers_through_the_existing_agent(tools, monkeypatch):
    """One end-to-end smoke test of the Streamlit script with a scripted model."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    import streamlit as st
    from pid_agent.ui import session

    final = 'P4711 is CentrifugalPump-1.\n\n```claims\n[{"predicate": "identified_as", "subject": "CentrifugalPump-1", "value": "P4711"}]\n```'
    llm = ScriptedLLM([call("find_entities", query="P4711")], final)
    monkeypatch.setattr(session, "build_agent", lambda settings, graph_tools: PidAgent(llm, graph_tools))
    st.cache_resource.clear()
    app = AppTest.from_file(str(PROJECT_ROOT / "src/pid_agent/ui/app.py"), default_timeout=60).run()
    assert not app.exception
    assert any("P&ID Engineering Assistant" in m.value for m in app.markdown)
    app.chat_input[0].set_value("What is P4711?").run()
    assert not app.exception
    rendered = " ".join(m.value for m in app.markdown)
    assert "P4711 is CentrifugalPump-1." in rendered and "```" not in rendered
    assert "Grounded: every claim matched graph evidence" in rendered
    assert "identified_as(CentrifugalPump-1, = P4711)" in rendered and "plant_graph" in rendered  # claim -> evidence -> graph source
    assert len(llm.calls) == 2  # exactly one agent run; nothing else called the model
    st.cache_resource.clear()
