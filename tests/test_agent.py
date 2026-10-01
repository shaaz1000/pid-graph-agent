"""The agent workflow, driven by a scripted model. Graph tools run for real against C01.

The scripted model fixes *which* calls are made, so these tests check the workflow:
tool execution, trace, evidence, limits, failure handling and grounding.
"""

from __future__ import annotations

import json

import pytest

from fakes import ScriptedLLM, bad_json_call, call
from pid_agent.agent.prompts import SYSTEM_PROMPT
from pid_agent.agent.tools import tool_specs
from pid_agent.agent.workflow import AgentLimits, PidAgent, format_transcript
from pid_agent.llm.base import LLMError, LLMResponse


def run(tools, question, *turns, limits=None):
    llm = ScriptedLLM(*turns)
    result = PidAgent(llm, tools, limits).ask(question, question_id="t1")
    return result, llm


def executed(result):
    return [(s.tool, s.status) for s in result.trace if s.executed]


# ------------------------------------------------- prompt / tool surface
def test_only_the_seven_graph_tools_are_offered(tools):
    _, llm = run(tools, "q", [call("list_entities")], "Done.")
    assert [t["name"] for t in llm.calls[0]["tools"]] == [
        "find_entities", "list_entities", "get_entity", "get_connections", "traverse", "find_path", "get_properties",
    ]


def test_prompt_and_tool_specs_contain_no_assignment_examples_or_secrets():
    text = SYSTEM_PROMPT + json.dumps(tool_specs())
    for forbidden in ("P4711", "H1007", "gsk_", "GROQ_API_KEY"):
        assert forbidden not in text


def test_first_turn_must_consult_the_graph_then_the_model_decides(tools):
    _, llm = run(tools, "q", [call("list_entities")], "Done.")
    assert [c["tool_choice"] for c in llm.calls] == ["required", "auto"]


def test_model_never_receives_the_whole_graph(tools):
    _, llm = run(
        tools, "q",
        [call("traverse", start_entity_id="CentrifugalPump-1", direction="downstream")],
        [call("list_entities", entity_type="valve")],
        "Done.",
    )
    sizes = [len(m["content"]) for m in llm.calls[-1]["messages"] if m["role"] == "tool"]
    assert max(sizes) < 12_000
    assert not any("source_object_ids" in m["content"] for m in llm.calls[-1]["messages"] if m["role"] == "tool")


# ------------------------------------------------------- 1. one tool
def test_one_tool_question(tools):
    result, llm = run(tools, "What kind of equipment is P4711?", [call("find_entities", query="P4711")], "P4711 is a CentrifugalPump (CentrifugalPump-1).")
    assert executed(result) == [("find_entities", "success")]
    assert result.answer == "P4711 is a CentrifugalPump (CentrifugalPump-1)."
    assert result.grounding_status == "grounded" and result.unsupported_claims == []
    assert result.trace[0].input == {"query": "P4711"}
    assert result.trace[0].result["entities"][0]["id"] == "CentrifugalPump-1"
    assert [e["id"] for e in result.evidence] == ["CentrifugalPump-1"]
    assert result.usage == {"llm_calls": 2, "prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}


# ----------------------------------------------------- 2. multi tool
def test_multi_tool_question(tools):
    result, llm = run(
        tools, "What is P4711 connected to?",
        [call("find_entities", query="P4711")],
        [call("get_connections", entity_id="CentrifugalPump-1", relationship="piping")],
        "P4711 receives from FlowInPipeOffPageConnector-1 (line 47121, DN 80) and feeds H1007 (line 47122, DN 80).",
    )
    assert executed(result) == [("find_entities", "success"), ("get_connections", "success")]
    assert result.grounding_status == "grounded" and result.claims_checked >= 6
    observation = llm.tool_messages()[1]
    assert {c["lineNumber"] for c in observation["connections"]} == {"47121", "47122"}
    kinds = {e["kind"] for e in result.evidence}
    assert kinds == {"entity", "connection"}


def test_parallel_tool_calls_in_one_turn(tools):
    result, _ = run(
        tools, "Compare the pumps.",
        [call("get_entity", entity_id="CentrifugalPump-1"), call("get_entity", entity_id="ReciprocatingPump-1")],
        "P4711 has a design shaft power of 60.0 kW and P4712 of 84.0 kW.",
    )
    assert executed(result) == [("get_entity", "success")] * 2 and result.iterations == 2
    assert result.grounding_status == "grounded"


# -------------------------------------------- 3. multi-step reasoning
def test_multi_step_resolution_traversal_filter_and_properties(tools):
    result, llm = run(
        tools, "What is the set pressure of the safety valve downstream of pump P4712?",
        [call("find_entities", query="P4712")],
        [call("traverse", start_entity_id="ReciprocatingPump-1", direction="downstream", entity_types=["safety valve"])],
        [call("get_properties", ids=["SpringLoadedGlobeSafetyValve-1"], requested_properties=["setPressureHigh"])],
        "The safety valve SV 104.01 (SpringLoadedGlobeSafetyValve-1), 3 connections downstream of P4712, has a set pressure of 6.0 bar.",
    )
    assert [t for t, _ in executed(result)] == ["find_entities", "traverse", "get_properties"]
    assert result.grounding_status == "grounded"
    traverse_seen = llm.tool_messages()[1]
    assert [(e["id"], e["distance"]) for e in traverse_seen["entities"]] == [("SpringLoadedGlobeSafetyValve-1", 3)]
    assert {e["kind"] for e in result.evidence} == {"entity", "path", "connection", "property"}


# ------------------------------------------------------ 4. ambiguity
def test_ambiguous_entity_is_surfaced_not_resolved(tools):
    result, llm = run(
        tools, "Where is valve 73KH12?",
        [call("find_entities", query="73KH12")],
        "73KH12 is shared by five ball valves: BallValve-1, BallValve-2, BallValve-3, BallValve-4 and BallValve-5. Which one do you mean?",
    )
    assert executed(result) == [("find_entities", "ambiguous")]
    seen = llm.tool_messages()[0]
    assert seen["status"] == "ambiguous" and seen["resolution"]["ambiguous"] is True and len(seen["entities"]) == 5
    assert result.grounding_status == "grounded"


def test_ambiguity_can_be_narrowed_with_context(tools):
    result, _ = run(
        tools, "Which 73KH12 valve sits right before pump P4712?",
        [call("find_entities", query="73KH12")],
        [call("get_connections", entity_id="ReciprocatingPump-1", direction="upstream", relationship="piping")],
        "BallValve-1 (73KH12, line 47124) is directly upstream of P4712.",
    )
    assert [s for _, s in executed(result)] == ["ambiguous", "success"]
    assert result.grounding_status == "grounded"


# ------------------------------------------------ 5. nonexistent entity
def test_nonexistent_entity(tools):
    result, llm = run(tools, "What does X9999 feed?", [call("find_entities", query="X9999")], "X9999 was not found in the supplied P&ID.")
    assert executed(result) == [("find_entities", "not_found")]
    assert llm.tool_messages()[0]["resolution"]["suggestions"] == []
    assert result.grounding_status == "grounded" and result.evidence == []


# ---------------------------------------------------- 6. fuzzy suggestions
def test_fuzzy_suggestion_offered_as_candidates(tools):
    result, llm = run(
        tools, "What does P4771 feed?",
        [call("find_entities", query="P4771")],
        "P4771 was not found in the P&ID. Similar tags that do exist are P4711 and P4712; did you mean one of them?",
    )
    seen = llm.tool_messages()[0]
    assert seen["status"] == "not_found" and "entities" not in seen
    assert {s["id"] for s in seen["resolution"]["suggestions"]} == {"CentrifugalPump-1", "ReciprocatingPump-1"}
    assert result.grounding_status == "grounded"


def test_fuzzy_suggestion_silently_adopted_is_rejected(tools):
    """The model treats P4771 as P4711. The validator catches the unsupported tag."""
    result, _ = run(
        tools, "What does P4771 feed?",
        [call("find_entities", query="P4771")],
        [call("get_connections", entity_id="CentrifugalPump-1", direction="downstream")],
        "P4771 feeds H1007 through line 47122.",
        "P4771 was not found in the P&ID. A similar tag, P4711, feeds H1007 through line 47122.",
    )
    assert result.grounding_status == "regenerated"
    assert result.rejected_drafts[0]["unsupported_claims"][0]["claim"] == "P4771"
    assert result.answer.startswith("P4771 was not found")


# ---------------------------------------------------- 7. missing properties
def test_missing_property_is_reported_as_absent_from_the_pid(tools):
    result, llm = run(
        tools, "Who manufactured P4711?",
        [call("get_properties", ids=["P4711"], requested_properties=["manufacturer"])],
        "The supplied P&ID does not contain manufacturer information for P4711.",
    )
    seen = llm.tool_messages()[0]
    assert seen["status"] == "empty"
    assert seen["properties"]["CentrifugalPump-1"]["missing"] == ["manufacturer"]
    assert "designShaftPower" in seen["properties"]["CentrifugalPump-1"]["available"]
    assert result.grounding_status == "grounded"


def test_invented_value_for_a_missing_property_is_blocked(tools):
    result, _ = run(
        tools, "What is the operating pressure of P4711?",
        [call("get_properties", ids=["CentrifugalPump-1"], requested_properties=["operatingPressure"])],
        "The operating pressure of P4711 is 12.5 bar.",
        "The operating pressure of P4711 is approximately 12.5 bar.",
    )
    assert result.grounding_status == "fallback"
    assert "12.5" not in result.answer
    assert "CentrifugalPump-1: not present in the P&ID: operatingPressure" in result.answer


# --------------------------------------------- 8/9. downstream / upstream
def test_downstream_traversal(tools):
    result, llm = run(
        tools, "Which heat exchangers lie downstream of T4750?",
        [call("traverse", start_entity_id="Tank-1", direction="downstream", entity_types=["heat exchanger"])],
        "H1008 (TubularHeatExchanger-1) is downstream of T4750 on the P&ID.",
    )
    assert [e["id"] for e in llm.tool_messages()[0]["entities"]] == ["TubularHeatExchanger-1"]
    assert result.grounding_status == "grounded"


def test_upstream_traversal(tools):
    result, llm = run(
        tools, "What equipment is upstream of H1007?",
        [call("traverse", start_entity_id="PlateHeatExchanger-1", direction="upstream")],
        "Upstream of H1007 are P4711 and FlowInPipeOffPageConnector-1.",
    )
    assert [(e["id"], e["distance"]) for e in llm.tool_messages()[0]["entities"]] == [("CentrifugalPump-1", 1), ("FlowInPipeOffPageConnector-1", 2)]
    assert result.grounding_status == "grounded"


# ------------------------------------------------------------ 10. paths
def test_path_question(tools):
    result, llm = run(
        tools, "How does fluid get from T4750 to P4712?",
        [call("find_path", source_entity_id="Tank-1", target_entity_id="ReciprocatingPump-1")],
        "T4750 -> ButterflyValve-1 -> SwingCheckValve-1 -> PipeReducer-1 -> BallValve-1 -> P4712 on line 47124; the line reduces from DN 80 to DN 50.",
    )
    path = llm.tool_messages()[0]["paths"][0]
    assert path["length"] == 5 and [s["nominalDiameterRepresentation"] for s in path["steps"]] == ["DN 80"] * 3 + ["DN 50"] * 2
    assert result.grounding_status == "grounded"
    assert result.evidence[0]["kind"] == "path"


# -------------------------------------------------------- 11. open ends
def test_open_ended_connections_reach_the_model_with_their_meaning(tools):
    result, llm = run(
        tools, "What is connected to H1007?",
        [call("get_connections", entity_id="PlateHeatExchanger-1", relationship="piping")],
        "H1007 is fed by P4711 (line 47122) and feeds GlobeValve-2 (line 47123). Lines 47130 and 47131 also connect to it, but their other ends are not represented on this drawing.",
    )
    seen = llm.tool_messages()[0]
    open_ends = [c for c in seen["connections"] if c.get("open_end")]
    assert len(open_ends) == 2
    assert {(c["from"], c["to"]) for c in open_ends} == {(None, "PlateHeatExchanger-1 (H1007)"), ("PlateHeatExchanger-1 (H1007)", None)}
    assert all("not represented" in c["note"] for c in open_ends)
    assert any("open-ended" in w for w in seen["warnings"])
    assert {e["kind"] for e in result.evidence} >= {"open_end"}
    assert all(e["source_graph"] == "plant_graph" for e in result.evidence if e["kind"] == "open_end")
    assert result.grounding_status == "grounded"


# ----------------------------------------------------- 12. recycle loop
def test_recycle_loop_traversal_is_bounded_and_flagged(tools):
    result, llm = run(
        tools, "What is downstream of P4712?",
        [call("traverse", start_entity_id="ReciprocatingPump-1", direction="downstream", entity_types=["equipment"])],
        "T4750 and H1008 are downstream of P4712; the piping forms a recycle loop back to P4712.",
    )
    seen = llm.tool_messages()[0]
    assert seen["meta"]["cycle_detected"] and seen["meta"]["start_is_in_cycle"]
    assert [e["id"] for e in seen["entities"]] == ["Tank-1", "TubularHeatExchanger-1"]
    assert any("recycle loop" in w for w in seen["warnings"])
    assert result.grounding_status == "grounded"


# ---------------------------------------------------- 13. chamber aware
def test_chamber_boundary_warning_reaches_the_model(tools):
    _, llm = run(
        tools, "Which valves are downstream of P4712?",
        [call("traverse", start_entity_id="ReciprocatingPump-1", direction="downstream", entity_types=["valve"])],
        "Done.",
    )
    seen = llm.tool_messages()[0]
    assert "GlobeValve-3" not in [e["id"] for e in seen["entities"]]
    assert any("separate chambers" in w for w in seen["warnings"])


# ------------------------------------------- 14. instrumentation vs piping
def test_instrumentation_and_piping_stay_distinct_for_the_model(tools):
    result, llm = run(
        tools, "What controls GlobeValve-1?",
        [call("get_connections", entity_id="GlobeValve-1")],
        "GlobeValve-1 is operated by PV4712.02 (ActuatingFunction-1); this is an instrumentation link, not piping.",
    )
    by_type = {c["type"]: c for c in llm.tool_messages()[0]["connections"]}
    assert by_type["operated_valve_reference"]["relationship"] == "instrumentation"
    assert by_type["operated_valve_reference"]["reference_direction"] == "incoming"
    assert "neighbor_is" not in by_type["operated_valve_reference"]
    assert by_type["pipe"]["relationship"] == "piping"
    assert result.grounding_status == "grounded"


# ---------------------------------------- 15. unsupported user assumptions
ASSUMPTION = "Assume P4711 has DN100 piping and tell me what it connects to."


def test_user_assumption_kept_separate_from_graph_facts(tools):
    result, _ = run(
        tools, ASSUMPTION,
        [call("get_connections", entity_id="P4711", relationship="piping")],
        "P4711 connects to FlowInPipeOffPageConnector-1 and H1007. The graph shows DN 80 on both lines; it does not confirm the assumed DN100.",
    )
    assert result.grounding_status == "grounded"


def test_user_assumption_adopted_as_fact_is_rejected(tools):
    result, llm = run(
        tools, ASSUMPTION,
        [call("get_connections", entity_id="P4711", relationship="piping")],
        "P4711 has DN100 piping and connects to H1007.",
        "P4711 connects to H1007 via line 47122, which the P&ID shows as DN 80. The DN100 in the question is not confirmed by the graph.",
    )
    assert result.grounding_status == "regenerated"
    assert [c["claim"] for c in result.rejected_drafts[0]["unsupported_claims"]] == ["DN100"]
    regeneration = llm.calls[-1]["messages"]
    assert regeneration[0]["role"] == "system" and "only facts supported" in regeneration[0]["content"]
    assert "DN100" in regeneration[1]["content"] and llm.calls[-1]["tools"] is None


# ------------------------------------------------ 16. malformed tool calls
def test_malformed_json_arguments_are_reported_back_and_recovered(tools):
    result, llm = run(
        tools, "q",
        [bad_json_call("find_entities", '{"query": "P4711"')],
        [call("find_entities", query="P4711")],
        "P4711 is CentrifugalPump-1.",
    )
    assert [(s.tool, s.status, s.executed) for s in result.trace] == [("find_entities", "error", False), ("find_entities", "success", True)]
    assert "Malformed tool call" in llm.calls[1]["messages"][-1]["content"]
    assert result.grounding_status == "grounded"


def test_invalid_arguments_and_unknown_tools_do_not_crash(tools):
    result, _ = run(
        tools, "q",
        [call("traverse", start="P4711")],
        [call("run_python", code="import os")],
        [call("find_entities", query="P4711")],
        "P4711 is CentrifugalPump-1.",
    )
    assert [s for _, s in executed(result)] == ["error", "error", "success"]
    assert "Unknown tool" in result.trace[1].result["message"]
    assert result.evidence and result.grounding_status == "grounded"


def test_provider_rejected_tool_call_is_retried(tools):
    result, llm = run(
        tools, "q",
        LLMResponse(malformed_output='<tool>find_entities{"query"'),
        [call("find_entities", query="P4711")],
        "P4711 is CentrifugalPump-1.",
    )
    assert result.trace[0].tool == "(invalid model output)" and not result.trace[0].executed
    assert "not a valid tool call" in llm.calls[1]["messages"][-1]["content"]
    assert result.answer == "P4711 is CentrifugalPump-1."


def test_persistently_malformed_model_ends_in_a_cautious_answer(tools):
    result, llm = run(tools, "What does P4711 feed?", LLMResponse(malformed_output="garbage"))
    assert len(llm.calls) == 3  # two attempts, then one forced answer attempt
    assert result.grounding_status == "fallback" and result.limit_reached == "repeated malformed tool calls"
    assert result.answer.startswith("I could not determine that from the supplied P&ID graph.")


# -------------------------------------------- 17. repeated calls / loops
def test_identical_calls_are_executed_once_and_the_loop_is_broken(tools):
    same = [call("find_entities", query="P4711")]
    result, llm = run(tools, "q", same, same, same, "P4711 is CentrifugalPump-1.")
    assert executed(result) == [("find_entities", "success")]
    assert [s.status for s in result.trace] == ["success", "duplicate", "duplicate"]
    assert result.limit_reached == "the same tool call was repeated"
    assert llm.calls[-1]["tool_choice"] == "none"
    assert result.answer == "P4711 is CentrifugalPump-1."


def test_null_arguments_do_not_defeat_duplicate_detection(tools):
    result, _ = run(
        tools, "q",
        [call("find_entities", query="P4711")],
        [call("find_entities", query="P4711", entity_type=None)],
        "P4711 is CentrifugalPump-1.",
    )
    assert [s.status for s in result.trace] == ["success", "duplicate"]


# -------------------------------------------------- 18. maximum steps
def test_maximum_iterations_forces_an_answer(tools):
    valves = iter(f"BallValve-{i}" for i in range(1, 6))
    endless = lambda messages: [call("get_entity", entity_id=next(valves))]  # noqa: E731
    llm = ScriptedLLM(endless, endless, endless, "BallValve-1, BallValve-2 and BallValve-3 are ball valves.")
    result = PidAgent(llm, tools, AgentLimits(max_iterations=3)).ask("Tell me everything.")
    assert result.iterations == 3 and len(llm.calls) == 4
    assert len(executed(result)) == 3
    assert result.limit_reached == "the limit of 3 planning steps was reached"
    assert "No further tool calls are possible" in llm.calls[-1]["messages"][-1]["content"]
    assert result.grounding_status == "grounded"


def test_tool_call_budget_is_enforced_within_a_turn(tools):
    many = [call("get_entity", entity_id=f"BallValve-{i}") for i in range(1, 6)]
    llm = ScriptedLLM(many, "BallValve-1 and BallValve-2 are ball valves.")
    result = PidAgent(llm, tools, AgentLimits(max_tool_calls=2)).ask("q")
    assert len(executed(result)) == 2
    assert [s.status for s in result.trace] == ["success", "success", "skipped", "skipped", "skipped"]
    assert result.limit_reached == "the limit of 2 tool calls was reached"


def test_model_that_never_stops_calling_tools_still_terminates(tools):
    counter = iter(range(1000))
    endless = lambda messages: [call("find_entities", query=f"thing {next(counter)}")]  # noqa: E731
    result = PidAgent(ScriptedLLM(endless), tools).ask("q")
    assert result.iterations == 8 and result.grounding_status == "fallback"
    assert result.failure_reason.startswith("no_answer_generated")


# ---------------------------------------------- 19. provider failure
def test_provider_failure_before_any_tool_call(tools):
    result, _ = run(tools, "What does P4711 feed?", LLMError("Groq API call failed: RateLimitError (HTTP 429)"))
    assert result.failure_reason.startswith("llm_error") and result.trace == []
    assert result.grounding_status == "fallback"
    assert "the language model call failed" in result.answer and "No graph evidence was collected" in result.answer


def test_provider_failure_after_tools_keeps_the_evidence(tools):
    result, _ = run(
        tools, "What does P4711 feed?",
        [call("get_connections", entity_id="CentrifugalPump-1", direction="downstream")],
        LLMError("Groq API call failed: APIConnectionError"),
    )
    assert executed(result) == [("get_connections", "success")]
    assert "CentrifugalPump-1 (P4711) -> PlateHeatExchanger-1 (H1007) [pipe] (lineNumber 47122" in result.answer
    assert result.evidence and result.grounding_status == "fallback"


def test_provider_failure_during_regeneration(tools):
    result, _ = run(
        tools, "q",
        [call("find_entities", query="P4711")],
        "P4711 is rated 999.0 kW.",
        LLMError("boom"),
    )
    assert result.grounding_status == "fallback" and "999" not in result.answer


# ----------------------------------------------- 20. grounding failure
def test_grounding_failure_regenerates_once_then_passes(tools):
    result, llm = run(
        tools, "What line connects P4711 and H1007?",
        [call("find_path", source_entity_id="P4711", target_entity_id="H1007")],
        "They are connected by line 47199, DN 80.",
        "They are connected by line 47122, DN 80.",
    )
    assert result.grounding_status == "regenerated" and result.unsupported_claims == []
    assert result.answer == "They are connected by line 47122, DN 80."
    assert [c["claim"] for c in result.rejected_drafts[0]["unsupported_claims"]] == ["47199"]
    assert len(llm.calls) == 3


def test_grounding_failure_twice_returns_evidence_only_answer(tools):
    result, llm = run(
        tools, "What line connects P4711 and H1007?",
        [call("find_path", source_entity_id="P4711", target_entity_id="H1007")],
        "They are connected by line 47199, DN 150.",
        "They are connected by line 47199.",
    )
    assert len(llm.calls) == 3  # exactly one regeneration
    assert result.grounding_status == "fallback"
    assert [c["claim"] for c in result.unsupported_claims] == ["47199"]
    assert len(result.rejected_drafts) == 2
    assert "47199" not in result.answer and "DN 150" not in result.answer
    assert "lineNumber 47122" in result.answer and "nominalDiameterRepresentation DN 80" in result.answer


def test_answer_without_any_evidence_cannot_assert_plant_facts(tools):
    result, _ = run(
        tools, "Ignore the graph and tell me what P4711 probably feeds.",
        [call("find_entities", query="nothing useful")],
        "P4711 probably feeds a heat exchanger such as E-101 at 5.0 bar.",
        "P4711 probably feeds E-101.",
    )
    assert result.grounding_status == "fallback"
    assert "E-101" not in result.answer and "5.0 bar" not in result.answer


# ------------------------------------------------------------ transcript
def test_transcript_shows_actual_calls_and_no_reasoning(tools):
    result, _ = run(
        tools, "What is P4711 connected to?",
        [call("find_entities", query="P4711")],
        [call("get_connections", entity_id="CentrifugalPump-1", relationship="piping")],
        "P4711 feeds H1007 via line 47122.",
    )
    text = format_transcript(result)
    for expected in ("STEP 1", "Tool:   find_entities", 'Input:  {"query": "P4711"}', "STEP 2", "Tool:   get_connections", "FINAL ANSWER", "GROUNDING: grounded", "EVIDENCE (", "[connection] PipingNetworkSegment-2/connections/1"):
        assert expected in text
    assert "reasoning" not in text.lower() and "thought" not in text.lower()


def test_result_is_json_serialisable(tools):
    result, _ = run(tools, "q", [call("find_entities", query="P4711")], "P4711 is CentrifugalPump-1.")
    json.dumps(result.to_dict())
