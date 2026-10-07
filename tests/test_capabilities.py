"""Capability-constrained planning, complete composite results and route semantics.

No model, no network. The three mechanisms come from declarations (which operation produces
which kind of output) and from the tool results; nothing depends on how a question is worded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fakes import ScriptedLLM, call
from pid_agent.agent import capabilities
from pid_agent.agent.answer import EvidenceRegistry, validate_submission
from pid_agent.agent.evidence_refs import annotate_refs
from pid_agent.agent.tools import requested_outputs
from pid_agent.agent.workflow import PidAgent

ROOT = Path(__file__).resolve().parents[1]
P12, TANK, VALVE = "ReciprocatingPump-1", "Tank-1", "ButterflyValve-1"


def observe(tools, *calls):
    return [annotate_refs(tools.call(name, arguments).to_dict(), step) for step, (name, arguments) in enumerate(calls, start=1)]


def outputs(*kinds):
    return [{"id": f"q{i}", "description": f"output {i}", "kind": kind} for i, kind in enumerate(kinds, start=1)]


def submit(obs, requested, facts=(), unknowns=()):
    """facts: (evidence id, covered output ids). Returns the validated submission."""
    cited = [{"ref": ref, "covers": list(covers)} for ref, covers in facts]
    return validate_submission({"direct_facts": cited, "unknowns": list(unknowns)}, obs, requested=requested)


def predicates(submission):
    return [f["p"] for item in [*submission.direct, *submission.derived] for f in item["facts"]]


# ================================================================== 1. planning from the kind of output
@pytest.mark.parametrize(
    ("kind", "wordings", "operations"),
    [
        ("boundary", ["the valves that shut this item off", "what must be closed around the exchanger", "isolation points, any gaps"], ["isolation_boundary"]),
        ("signal_chain", ["where the controller measures and what it moves", "sensor, final element and fail action", "the whole loop"], ["trace_instrumentation"]),
        ("line_structure", ["each branch of the line and its size", "where the header splits"], ["trace_line"]),
        ("flow_reachability", ["what the pump feeds", "equipment downstream once the valve is shut", "what still reaches the vessel"], ["traverse", "find_path"]),
        ("connectivity", ["are the two joined by pipe at all", "any piping between them"], ["find_path", "traverse", "get_connections", "trace_line", "isolation_boundary"]),
    ],
)
def test_the_same_kind_of_output_gets_the_same_operations_whatever_the_wording(kind, wordings, operations):
    plans = [requested_outputs({"requested_outputs": [{"description": text, "kind": kind}]})[0][0] for text in wordings]
    assert len({plan["how_to_answer"] for plan in plans}) == 1  # the description plays no part
    assert [name.split(" ")[0] for name in capabilities.compatible_operations(kind)] == operations
    assert all(name.split(" ")[0] in plans[0]["how_to_answer"] for name in operations)


def test_kinds_a_drawing_does_not_contain_and_open_kinds():
    plan, problem = requested_outputs({"requested_outputs": [{"description": "the order to close them", "kind": "procedure_or_behaviour"}, {"description": "which pumps", "kind": "items"}]})
    assert problem is None and "A P&ID does not contain this" in plan[0]["how_to_answer"] and plan[1]["how_to_answer"] == "Any graph operation can answer it."
    assert not requested_outputs({"requested_outputs": [{"description": "x", "kind": "isolate"}]})[0]  # only the declared kinds exist
    assert capabilities.answers("items", "traverse", "drawn_flow") and capabilities.answers("property", "get_connections", None)


def test_the_planner_is_told_the_compatible_operations_after_decomposing(tools):
    asked = [call("decompose_request", requested_outputs=[{"description": "boundary", "kind": "boundary"}, {"description": "reach", "kind": "flow_reachability"}])]
    agent = PidAgent(llm := ScriptedLLM(asked, [call("isolation_boundary", entity_id="T4750")], [call("submit_answer", derived_facts=["R2"])]), tools, answer_mode="structured")
    agent.ask("q", question_id="t")
    shown = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert [o["how_to_answer"] for o in shown["requested_outputs"]] == [
        "Answered by a result of: isolation_boundary.",
        "Answered by a result of: traverse (along the drawn flow direction (direction downstream or upstream)), find_path (along the drawn flow direction (direction downstream or upstream)).",
    ]


# ================================================================== 2. an incompatible result does not answer an output
def test_adjacency_rows_do_not_answer_a_boundary(tools):
    obs = observe(tools, ("get_connections", {"entity_id": "P4712", "relationship": "piping"}), ("isolation_boundary", {"entity_id": "P4712"}))
    rejected = submit(obs, outputs("boundary"), [("R1", ["q1"])])
    assert not rejected.ok and "is of kind boundary. The rows cited for it come from get_connections, which cannot answer that kind. Answered by a result of: isolation_boundary. Or mark it unknown." in rejected.errors[0]
    assert submit(obs, outputs("boundary"), [("R2", ["q1"])]).ok
    assert submit(obs, outputs("boundary"), [("R1", ["q1"])], [{"category": "not_represented", "covers": ["q1"]}]).ok  # or it is declared unknown


def test_single_links_do_not_answer_a_signal_chain(tools):
    obs = observe(tools, ("get_connections", {"entity_id": "PICSA4712.02", "relationship": "instrumentation"}), ("trace_instrumentation", {"entity_id": "PICSA4712.02"}))
    rejected = submit(obs, outputs("signal_chain"), [("R1", ["q1"])])
    assert not rejected.ok and "Answered by a result of: trace_instrumentation." in rejected.errors[0]
    assert submit(obs, outputs("signal_chain"), [("R2", ["q1"])]).ok


def test_open_kinds_accept_any_operation_and_one_output_needs_no_covers(tools):
    obs = observe(tools, ("get_connections", {"entity_id": "P4712", "relationship": "piping"}))
    assert submit(obs, outputs("adjacency"), [("R1", [])]).ok and submit(obs, outputs("items", "property"), [("R1", ["q1", "q2"])]).ok
    assert not submit(obs, outputs("boundary"), [("R1", [])]).ok  # one thing asked, but still of a kind adjacency cannot answer


# ================================================================== 3. a composite result is complete whatever was cited
def test_one_cited_boundary_row_brings_the_whole_boundary(tools):
    obs = observe(tools, ("isolation_boundary", {"entity_id": "P4712"}))
    one_valve = obs[0]["derived"][0]["ref"]
    answer = submit(obs, outputs("boundary"), [(one_valve, ["q1"])])
    assert answer.ok
    found = predicates(answer)
    assert found.count("isolation_boundary_valve") == 4 and found.count("relief_device_on_boundary") == 1  # the relief line is not left out
    assert "fully_valve_bounded" in found and "relief_path_inside_boundary" in found
    assert "closed_end_in_region" not in found and "is_a" not in found  # nothing outside the kind is added
    added = [item for item in answer.derived if item.get("added_by_application")]
    assert len(added) == 6 and all(item["covers"] == ["q1"] for item in added)
    assert answer.requested[0]["covered_by"]["completed_by_application"] == [item["ref"] for item in added]
    assert "SV 104.01 (SpringLoadedGlobeSafetyValve-1) is connected to the piping around P4712" in answer.render()
    assert any("added by the application" in note for note in answer.notes)


def test_gaps_are_part_of_a_boundary(tools):
    obs = observe(tools, ("isolation_boundary", {"entity_id": "H1008"}))
    answer = submit(obs, outputs("boundary"), [(obs[0]["derived"][0]["ref"], ["q1"])])
    assert predicates(answer).count("unisolated_connection") == 2 and predicates(answer).count("isolation_boundary_valve") == 4


def test_one_cited_link_brings_the_whole_loop_including_the_final_element(tools):
    obs = observe(tools, ("trace_instrumentation", {"entity_id": "PICSA4712.02"}))
    first_link = obs[0]["connections"][0]["ref"]
    answer = submit(obs, outputs("signal_chain"), [(first_link, ["q1"])])
    found = predicates(answer)
    assert answer.ok and {"senses_at", "measurement_input_to", "sends_signal_to", "operates", "signal_chain", "loop_measured_at", "loop_acts_on"} <= set(found)
    acts = next(f for item in answer.derived for f in item["facts"] if f["p"] == "loop_acts_on")
    assert acts["o"] == "GlobeValve-1" and acts["q"]["fail_action"] == "fail close" and acts["q"]["line"] == "47127"
    property_rows = {item["ref"] for report in obs[0]["properties"].values() for item in report["found"]}
    assert property_rows and not property_rows & {item["ref"] for item in [*answer.direct, *answer.derived]}  # the property rows of the result are not part of the chain


def test_a_line_and_a_set_of_routes_are_completed_too(tools):
    obs = observe(tools, ("trace_line", {"line": "47126"}), ("find_path", {"source_entity_id": "P4712", "target_entity_id": "T4750", "all_paths": True}))
    run = next(row["ref"] for row in obs[0]["derived"] if row["predicate"] == "line_run")
    answer = submit(obs, outputs("line_structure", "flow_reachability"), [(run, ["q1"]), (obs[1]["paths"][0]["ref"], ["q2"])])
    assert answer.ok and predicates(answer).count("line_run") == 10 and predicates(answer).count("line_meets_line") == 5
    assert predicates(answer).count("path") == 2  # both routes of the result, not only the one that was cited


def test_rows_are_only_added_for_the_kind_that_was_asked(tools):
    obs = observe(tools, ("isolation_boundary", {"entity_id": "P4712"}))
    one_valve = obs[0]["derived"][0]["ref"]
    as_item = submit(obs, outputs("items"), [(one_valve, ["q1"])])
    assert as_item.ok and len(as_item.derived) == 1 and not any("added by the application" in n for n in as_item.notes)  # asked for an item, got the cited row and nothing more
    twice = submit(obs, outputs("boundary"), [("R1", ["q1"])])
    assert len({item["ref"] for item in twice.derived}) == len(twice.derived)  # nothing is added twice


# ================================================================== 4. topological connectivity is not drawn-flow reachability
SHUT = {"source_entity_id": "T4750", "target_entity_id": "P4712", "blocked_entity_ids": [VALVE]}


def test_a_route_carries_its_semantics(tools):
    flow, topo = tools.call("find_path", {"source_entity_id": "T4750", "target_entity_id": "P4712"}), tools.call("find_path", {**SHUT, "direction": "any"})
    assert flow.meta["route_semantics"] == "drawn_flow" and flow.paths[0]["route_semantics"] == "drawn_flow" and "pipes_against_flow" not in flow.paths[0]
    path = topo.paths[0]
    assert topo.meta["route_semantics"] == path["route_semantics"] == "topological"
    # the known case, from edge direction and device class alone: backwards through a relief device
    assert path["pipes_against_flow"] == 4 and path["one_way_devices_against_flow"] == ["SpringLoadedGlobeSafetyValve-1"]
    assert tools.call("find_path", {"source_entity_id": "P4712", "target_entity_id": "T4750", "direction": "upstream"}).meta["route_semantics"] == "drawn_flow"
    assert tools.call("traverse", {"start_entity_id": "T4750", "direction": "both"}).meta["route_semantics"] == "topological"
    assert tools.call("traverse", {"start_entity_id": "T4750", "direction": "downstream"}).entities[0]["route_semantics"] == "drawn_flow"


def test_a_check_valve_passed_backwards_is_named(tools):
    path = tools.call("find_path", {"source_entity_id": "P4712", "target_entity_id": "T4750", "direction": "any", "blocked_entity_ids": ["PipeTee-2"]}).paths[0]
    assert path["route_semantics"] == "topological" and "SwingCheckValve-1" in path["one_way_devices_against_flow"]


def test_a_topological_route_cannot_answer_flow_reachability_and_a_directional_one_can(tools):
    obs = observe(tools, ("find_path", {**SHUT, "direction": "any"}), ("find_path", SHUT), ("find_path", {"source_entity_id": "T4750", "target_entity_id": "P4712"}))
    topological = submit(obs, outputs("flow_reachability"), [("R1", ["q1"])])
    assert not topological.ok
    assert "is of kind flow_reachability. The rows cited for it come from find_path (topological), which cannot answer that kind." in topological.errors[0]
    assert "along the drawn flow direction" in topological.errors[0]
    # with the valve treated as closed there is no drawn-flow route: that status is the answer
    none = submit(obs, outputs("flow_reachability"), [("R2", ["q1"])])
    assert none.ok and {"p": "no_path", "s": TANK, "o": P12, "q": {"direction": "downstream", "blocked": [VALVE], "semantics": "drawn_flow"}} in none.facts()
    assert submit(obs, outputs("flow_reachability"), [("R3", ["q1"])]).ok
    # the same topological route remains valid evidence that the two are joined by piping
    connected = submit(obs, outputs("connectivity"), [("R1", ["q1"])])
    assert connected.ok and any(f["p"] == "path" and f["q"]["semantics"] == "topological" for f in connected.facts())


def test_a_topological_route_is_worded_as_connectivity(tools):
    obs = observe(tools, ("find_path", {**SHUT, "direction": "any"}))
    text = submit(obs, outputs("connectivity"), [("R1", ["q1"])]).render()
    assert "Connected by piping when flow direction is ignored (not a route in the drawn flow direction): T4750 (Tank-1) - SV 104.01" in text
    assert "4 of them against the drawn flow, passing SpringLoadedGlobeSafetyValve-1 against its flow direction (with ButterflyValve-1 treated as closed)" in text
    assert "->" not in text and "Route:" not in text


def test_reach_ignoring_flow_direction_is_not_flow_reachability_either(tools):
    obs = observe(tools, ("traverse", {"start_entity_id": "T4750", "direction": "both", "entity_types": ["equipment"]}), ("traverse", {"start_entity_id": "T4750", "direction": "downstream", "entity_types": ["equipment"]}))
    assert not submit(obs, outputs("flow_reachability"), [("R1", ["q1"])]).ok and submit(obs, outputs("flow_reachability"), [("R2", ["q1"])]).ok
    assert "connected to Tank-1 when flow direction is ignored" in submit(obs, outputs("connectivity"), [("R1", ["q1"])]).render()


def test_nothing_reachable_is_a_fact_that_can_be_cited(tools):
    obs = observe(tools, ("traverse", {"start_entity_id": "T4750", "direction": "downstream", "blocked_entity_ids": [VALVE]}))
    answer = submit(obs, outputs("flow_reachability"), [("E1.0", ["q1"])])
    assert answer.ok and {"p": "reaches_nothing", "s": TANK, "q": {"direction": "downstream", "blocked": [VALVE], "semantics": "drawn_flow"}} in answer.facts()
    assert EvidenceRegistry(obs).kind("E1.0") == "derived"


# ================================================================== 5. end to end, and nothing question-specific
def test_an_answer_that_cites_too_little_is_completed_and_one_from_the_wrong_operation_is_sent_back(tools):
    asked = [call("decompose_request", requested_outputs=[{"description": "what bounds it", "kind": "boundary"}, {"description": "in which order", "kind": "procedure_or_behaviour"}])]
    adjacency, boundary = [call("get_connections", entity_id="T4750", relationship="piping")], [call("isolation_boundary", entity_id="T4750")]
    wrong = [call("submit_answer", direct_facts=[{"ref": "R2", "covers": ["q1"]}], unknowns=[{"category": "operating_procedure", "covers": ["q2"]}])]
    little = [call("submit_answer", derived_facts=[{"ref": "E4.2", "covers": ["q1"]}], unknowns=[{"category": "operating_procedure", "covers": ["q2"]}])]  # one valve row of the boundary (step 4)
    agent = PidAgent(llm := ScriptedLLM(asked, adjacency, wrong, boundary, little), tools, answer_mode="structured")
    result = agent.ask("q", question_id="t")
    assert [s.status for s in result.trace if s.tool == "submit_answer"] == ["rejected", "accepted"] and result.grounding_status == "grounded"
    assert "cannot answer that kind" in next(s.result["problems"] for s in result.trace if s.status == "rejected")[0]
    assert result.answer.count("is the nearest valve on the") == 3 and "discharges into the piping around T4750" in result.answer
    assert "A P&ID does not contain operating procedures or sequences" in result.answer


def test_the_routing_logic_contains_nothing_from_any_question():
    source = (ROOT / "src" / "pid_agent" / "agent" / "capabilities.py").read_text()
    code = source.casefold()
    for term in ("t4750", "p4712", "p4711", "h1007", "h1008", "sv 104", "104.01", "picsa", "47126", "hg2", "blocked in", "trip", "which valves", "map all", "maintenance", "loses"):
        assert term not in code, term
    questions = [q["question"] for name in ("complex/questions.json", "holdout/questions.json") for q in json.loads((ROOT / "evals" / "followup" / name).read_text())["questions"]]
    assert not any(q.casefold() in code for q in questions)
    # the keys of the declaration are kinds of output and names of operations, nothing else
    from pid_agent.agent.tools import OUTPUT_KINDS, TOOL_ARGS

    kinds = set(OUTPUT_KINDS.__args__)
    assert set(capabilities.PRODUCERS) | capabilities.NOT_IN_A_DRAWING <= kinds
    assert {tool for producers in capabilities.PRODUCERS.values() for tool in producers} <= set(TOOL_ARGS)
    assert {(tool, kind) for tool, kind in capabilities.BUNDLES} <= {(tool, kind) for kind, producers in capabilities.PRODUCERS.items() for tool in producers}
    assert "import re" not in source
