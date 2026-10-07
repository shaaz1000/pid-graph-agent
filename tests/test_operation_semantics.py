"""What a cited result proves is decided by the operation, not by the model's label.

No model, no network. The kind the model gives a requested output is used for planning. These
tests give outputs the wrong kind on purpose and check that neither the completion of a
composite analysis nor the reading of a route depends on it.
"""

from __future__ import annotations

import pytest

from fakes import ScriptedLLM, call
from pid_agent.agent import capabilities
from pid_agent.agent.answer import validate_submission
from pid_agent.agent.evidence_refs import annotate_refs
from pid_agent.agent.tools import OUTPUT_KINDS, TOOL_ARGS
from pid_agent.agent.workflow import PidAgent

KINDS = sorted(OUTPUT_KINDS.__args__)
OPEN_KINDS = [k for k in KINDS if k not in capabilities.PRODUCERS and k not in capabilities.NOT_IN_A_DRAWING]
RELIEF = "SpringLoadedGlobeSafetyValve-1"
# From the tank to the pump with the tank outlet valve shut: the only piping left runs backwards through the relief valve.
BACKWARDS = {"source_entity_id": "T4750", "target_entity_id": "P4712", "blocked_entity_ids": ["ButterflyValve-1"], "direction": "any"}
LOOP = {"entity_id": "PICSA4712.02"}


def observe(tools, *calls):
    return [annotate_refs(tools.call(name, arguments).to_dict(), step) for step, (name, arguments) in enumerate(calls, start=1)]


def submit(obs, kind, *refs):
    requested = [{"id": "q1", "description": "what was asked", "kind": kind}]
    return validate_submission({"direct_facts": [{"ref": ref, "covers": ["q1"]} for ref in refs]}, obs, requested=requested)


def shown(submission):
    return {item["ref"] for item in [*submission.direct, *submission.derived]}


def record(submission):
    return submission.requested[0]["covered_by"]


# ================================================================== 1. a route that ignores flow direction is never flow evidence
def test_what_a_route_establishes_comes_from_its_semantics():
    assert capabilities.establishes("find_path", "topological") == ["connectivity"]
    assert capabilities.establishes("traverse", "topological") == ["connectivity"]
    assert capabilities.establishes("find_path", "drawn_flow") == ["connectivity", "flow_reachability"]
    assert capabilities.establishes("traverse", "drawn_flow") == ["connectivity", "flow_reachability"]
    for tool in TOOL_ARGS:  # no operation gives flow evidence without drawn-flow semantics
        assert "flow_reachability" not in capabilities.establishes(tool, "topological") and "flow_reachability" not in capabilities.establishes(tool, None)


@pytest.mark.parametrize("kind", KINDS)
def test_no_label_turns_a_backwards_route_through_a_relief_valve_into_flow(tools, kind):
    obs = observe(tools, ("find_path", BACKWARDS))
    path = obs[0]["paths"][0]
    assert path["route_semantics"] == "topological" and path["one_way_devices_against_flow"] == [RELIEF]
    answer = submit(obs, kind, "E1.1")
    assert record(answer)["route_evidence"] == [{"ref": "E1.1", "semantics": "topological", "establishes": ["connectivity"]}]
    if kind == "flow_reachability":  # the model said it is a flow question: the route does not answer it
        assert not answer.ok and "cannot answer that kind" in answer.errors[0]
    text = answer.render()
    assert "Connected by piping when flow direction is ignored (not a route in the drawn flow direction)" in text
    assert f"passing {RELIEF} against its flow direction" in text and "Route:" not in text and " -> " not in text
    assert all(f["q"]["semantics"] == "topological" for item in answer.derived for f in item["facts"] if f["p"] == "path")


@pytest.mark.parametrize("kind", ["items", "connectivity", "other", "adjacency"])
def test_reach_ignoring_flow_direction_is_not_flow_under_any_label(tools, kind):
    obs = observe(tools, ("traverse", {"start_entity_id": "P4712", "direction": "both", "entity_types": ["equipment"]}))
    answer = submit(obs, kind, "R1")
    assert answer.ok and record(answer)["route_evidence"] and all(row["establishes"] == ["connectivity"] for row in record(answer)["route_evidence"])
    assert "when flow direction is ignored" in answer.render() and "downstream of" not in answer.render() and "upstream of" not in answer.render()


@pytest.mark.parametrize("kind", ["flow_reachability", "items", "other"])
def test_a_route_along_the_drawn_flow_is_flow_evidence_whatever_the_label(tools, kind):
    obs = observe(tools, ("find_path", {"source_entity_id": "T4750", "target_entity_id": "P4712"}), ("traverse", {"start_entity_id": "P4712", "direction": "upstream", "entity_types": ["equipment"]}))
    answer = submit(obs, kind, "E1.1", "R2")
    assert answer.ok and len(record(answer)["route_evidence"]) > 1 and all(row["semantics"] == "drawn_flow" and "flow_reachability" in row["establishes"] for row in record(answer)["route_evidence"])
    assert "Route: " in answer.render() and "upstream of" in answer.render()  # the direction asked of the graph is the direction stated


def test_mixing_both_readings_keeps_each_row_worded_by_its_own_semantics(tools):
    obs = observe(tools, ("find_path", BACKWARDS), ("find_path", {"source_entity_id": "T4750", "target_entity_id": "P4712"}))
    answer = submit(obs, "flow_reachability", "E1.1", "E2.1")
    # each row keeps its own reading: the drawn-flow route does not lend flow to the topological one beside it
    assert answer.ok and {row["ref"]: row["establishes"] for row in record(answer)["route_evidence"]} == {"E1.1": ["connectivity"], "E2.1": ["connectivity", "flow_reachability"]}
    assert record(answer)["derived"] == ["E2.1"]  # only the drawn-flow route answers the flow output
    lines = answer.render().splitlines()
    assert sum("not a route in the drawn flow direction" in line for line in lines) == 1 and sum(line.startswith("- Route: ") for line in lines) == 1


# ================================================================== 2. a composite analysis is completed whatever the label
def core(obs, step=1):
    return set(capabilities.complete(obs[step - 1]["tool"], obs[step - 1]))


@pytest.mark.parametrize("kind", [*OPEN_KINDS, "signal_chain"])
def test_one_cited_row_of_a_loop_brings_the_loop_under_any_label(tools, kind):
    obs = observe(tools, ("trace_instrumentation", LOOP))
    one_link = obs[0]["connections"][0]["ref"]
    answer = submit(obs, kind, one_link)
    assert answer.ok and shown(answer) == core(obs)
    text = answer.render()
    for part in ("measurement point", "PT4712.02", "PV4712.02", "encoded fail action: fail close", "GlobeValve-1", "line 47126", "line 47127"):
        assert part in text, part
    assert record(answer)["completed_by_application"] and set(record(answer)["completed_by_application"]) == core(obs) - {one_link}


def test_the_answer_is_the_same_for_every_label(tools):
    obs = observe(tools, ("trace_instrumentation", LOOP))
    answers = {kind: submit(obs, kind, obs[0]["derived"][0]["ref"]).render() for kind in [*OPEN_KINDS, "signal_chain"]}
    assert len(set(answers.values())) == 1


@pytest.mark.parametrize("kind", [*OPEN_KINDS, "boundary", "connectivity"])
def test_one_cited_valve_brings_the_boundary_with_its_gaps_and_relief_rows(tools, kind):
    obs = observe(tools, ("isolation_boundary", {"entity_id": "T4750"}))
    answer = submit(obs, kind, obs[0]["derived"][0]["ref"])
    assert answer.ok and shown(answer) == core(obs)
    got = [f["p"] for item in answer.derived for f in item["facts"]]
    assert got.count("isolation_boundary_valve") == 3 and {"relief_device_on_boundary", "relief_path_inside_boundary", "fully_valve_bounded"} <= set(got)


def test_a_strict_label_still_rejects_the_wrong_operation(tools):
    obs = observe(tools, ("trace_instrumentation", LOOP))
    answer = submit(obs, "boundary", obs[0]["connections"][0]["ref"])
    assert not answer.ok and "cannot answer that kind" in answer.errors[0]  # the label may tighten the check; it never loosens it


# ================================================================== 3. the operation's result decides what is added
def test_completion_is_declared_per_operation_and_reads_only_the_result(tools):
    assert set(capabilities.CORE_ROWS) == {"isolation_boundary", "trace_instrumentation", "trace_line", "find_path"}
    obs = observe(tools, ("get_entity", {"entity_id": "P4712"}), ("get_connections", {"entity_id": "P4712", "relationship": "piping"}), ("traverse", {"start_entity_id": "P4712", "direction": "downstream"}),
                  ("trace_instrumentation", LOOP), ("find_path", {"source_entity_id": "T4750", "target_entity_id": "P4712", "all_paths": True}))  # fmt: skip
    assert [bool(capabilities.complete(result["tool"], result)) for result in obs] == [False, False, False, True, True]
    assert capabilities.complete("isolation_boundary", obs[3]) == []  # a result is read as what it is, not as what it is called
    loop = obs[3]
    assert set(capabilities.complete("trace_instrumentation", loop)) == {row["ref"] for row in loop["connections"]} | {row["ref"] for row in loop["derived"] if row["predicate"] in ("signal_chain", "loop_measured_at", "loop_acts_on")}
    assert set(capabilities.complete("find_path", obs[4])) == {row["ref"] for row in obs[4]["paths"]}


def test_rows_outside_the_cited_analysis_are_not_added(tools):
    obs = observe(tools, ("get_entity", {"entity_id": "P4712"}), ("isolation_boundary", {"entity_id": "T4750"}), ("trace_instrumentation", LOOP), ("get_connections", {"entity_id": "P4712", "relationship": "piping"}))
    answer = submit(obs, "items", obs[2]["connections"][0]["ref"], "E1.1")
    assert answer.ok and shown(answer) == core(obs, 3) | {"E1.1"}
    assert not any(ref.startswith(("E2.", "E4.")) for ref in shown(answer))  # other results stay out
    properties = {item["ref"] for report in obs[2]["properties"].values() for item in report["found"]}
    assert properties and not properties & shown(answer) and obs[2]["entities"][0]["ref"] not in shown(answer)  # so do the property and item rows of the same result


def test_a_single_lookup_is_never_completed(tools):
    obs = observe(tools, ("get_connections", {"entity_id": "P4712", "relationship": "piping"}))
    for kind in OPEN_KINDS:
        answer = submit(obs, kind, obs[0]["connections"][0]["ref"])
        assert answer.ok and len(shown(answer)) == 1 and not record(answer)["completed_by_application"]


# ================================================================== 4. end to end with a wrong decomposition
def ask(tools, kind, *turns):
    asked = [call("decompose_request", requested_outputs=[{"description": "what was asked", "kind": kind}])]
    return PidAgent(ScriptedLLM(asked, *turns), tools, answer_mode="structured").ask("q", question_id="t")


def test_end_to_end_a_flow_question_labelled_items_cannot_state_a_flow_route(tools):
    result = ask(tools, "items", [call("find_path", **BACKWARDS)], [call("submit_answer", derived_facts=[{"ref": "E2.1", "covers": ["q1"]}])])
    assert result.grounding_status == "grounded"
    assert "not a route in the drawn flow direction" in result.answer and f"passing {RELIEF} against its flow direction" in result.answer
    assert "Route:" not in result.answer and "->" not in result.answer


def test_end_to_end_a_loop_labelled_items_is_still_complete(tools):
    result = ask(tools, "items", [call("trace_instrumentation", **LOOP)], [call("submit_answer", direct_facts=[{"ref": "E2.2", "covers": ["q1"]}])])
    assert result.grounding_status == "grounded"
    for part in ("Signal chain:", "encoded fail action: fail close", "GlobeValve-1", "measurement point"):
        assert part in result.answer, part
