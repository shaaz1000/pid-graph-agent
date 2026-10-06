"""Follow-up round: graph analyses, structured answers, gold and the consistency evaluator.

No model, no network. The agent runs with a scripted model.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from fakes import ScriptedLLM, call
from pid_agent.agent import workflow
from pid_agent.agent.answer import EvidenceRegistry, validate_submission
from pid_agent.agent.evidence_refs import annotate_refs
from pid_agent.agent.prompts import STRUCTURED_SYSTEM_PROMPT
from pid_agent.agent.tools import GraphTools, submit_answer_spec, tool_specs
from pid_agent.agent.workflow import AgentLimits, PidAgent
from pid_agent.graph.analysis import piping_role
from pid_agent.graph.service import GraphService, same_value

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "data" / "dexpi-1.3-examples"
spec = importlib.util.spec_from_file_location("followup", ROOT / "evals" / "followup" / "followup.py")
followup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(followup)
QUESTIONS = json.loads(followup.COMPLEX.read_text())["questions"]
GROUPS = json.loads(followup.GROUPS.read_text())["groups"]


def derived(tools, name, **arguments):
    result = tools.call(name, arguments)
    assert result.status == "success", result.message
    return result


def objects(result, predicate):
    return {row.get("object") for row in result.derived if row["predicate"] == predicate}


def value(result, predicate):
    return next(row["value"] for row in result.derived if row["predicate"] == predicate)


# ================================================================== isolation boundary
def test_isolation_boundary_of_a_tank_and_what_cannot_be_isolated(tools):
    result = derived(tools, "isolation_boundary", entity_id="T4750")
    assert objects(result, "isolation_boundary_valve") == {"GlobeValve-1", "GlobeValve-2", "ButterflyValve-1"}
    relief = next(row for row in result.derived if row["predicate"] == "relief_device_on_boundary")
    # The safety valve discharges into the tank: it is connected without a valve, but it does not relieve the tank.
    assert relief["object"] == "SpringLoadedGlobeSafetyValve-1" and relief["qualifiers"]["relieves_region"] is False
    assert value(result, "fully_valve_bounded") is True and value(result, "relief_path_inside_boundary") is False


def test_boundary_passes_fittings_and_keeps_the_relief_device_of_the_region(tools):
    result = derived(tools, "isolation_boundary", entity_id="P4712")
    assert objects(result, "isolation_boundary_valve") == {"BallValve-1", "BallValve-2", "BallValve-3", "BallValve-4"}
    assert value(result, "fully_valve_bounded") is True and value(result, "relief_path_inside_boundary") is True
    assert {"PipeTee-1", "PipeTee-2", "PipeTee-3"} <= set(result.meta["region_entities"])


def test_connections_without_a_valve_are_reported_not_guessed(tools):
    result = derived(tools, "isolation_boundary", entity_id="H1007")
    kinds = sorted((row["qualifiers"]["kind"], row.get("object")) for row in result.derived if row["predicate"] == "unisolated_connection")
    assert kinds == [("equipment", "CentrifugalPump-1"), ("open_end", None), ("open_end", None)]
    assert value(result, "fully_valve_bounded") is False
    exchanger = derived(tools, "isolation_boundary", entity_id="H1008")
    assert "FlowOutPipeOffPageConnector-1" in objects(exchanger, "unisolated_connection")


def test_a_check_valve_is_not_a_shut_off_valve(tools):
    result = derived(tools, "isolation_boundary", entity_id="PipeReducer-1")
    assert objects(result, "check_valve_on_boundary") == {"SwingCheckValve-1"} and value(result, "fully_valve_bounded") is False
    assert piping_role(tools._service.index.entities["SwingCheckValve-1"]) == "check_valve"
    assert piping_role(tools._service.index.entities["SpringLoadedGlobeSafetyValve-1"]) == "relief_device"


def test_every_derived_row_carries_its_operation_and_provenance(tools):
    for name, arguments in (("isolation_boundary", {"entity_id": "T4750"}), ("trace_instrumentation", {"entity_id": "PICSA4712.02"}), ("trace_line", {"line": "47126"})):
        result = tools.call(name, arguments)
        assert result.derived
        for row in result.derived:
            assert row["operation"] == name and row["parameters"] and row["statement"] and (row["source_entities"] or row["source_connections"])


# ================================================================== blocked items and all routes
def test_reachability_with_items_treated_as_closed(tools):
    open_ = {e["id"] for e in tools.call("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"]}).entities}
    shut = tools.call("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"], "blocked_entity_ids": ["BallValve-4"]})
    assert open_ == {"Tank-1", "TubularHeatExchanger-1"} and {e["id"] for e in shut.entities} == {"Tank-1"}
    assert shut.meta["blocked"] == ["BallValve-4"] and shut.meta["blocked_reached"] == ["BallValve-4"]
    none = tools.call("find_path", {"source_entity_id": "P4711", "target_entity_id": "T4750", "blocked_entity_ids": ["GlobeValve-2"]})
    assert none.status == "empty" and none.meta["no_path"]["blocked"] == ["GlobeValve-2"]
    assert tools.call("find_path", {"source_entity_id": "P4711", "target_entity_id": "T4750", "blocked_entity_ids": ["T4750"]}).status == "error"


def test_all_routes_between_two_items_with_what_lies_on_each(tools):
    result = tools.call("find_path", {"source_entity_id": "P4712", "target_entity_id": "T4750", "all_paths": True})
    assert result.meta["path_count"] == 2 and result.meta["shortest_path_only"] is False
    relief, process = result.paths
    assert relief["relief_devices"] == ["SpringLoadedGlobeSafetyValve-1"] and "shut_off_valves" not in relief
    assert process["shut_off_valves"] == ["BallValve-4", "GlobeValve-1"] and process["equipment"] == ["TubularHeatExchanger-1"]
    left = tools.call("find_path", {"source_entity_id": "P4712", "target_entity_id": "T4750", "all_paths": True, "blocked_entity_ids": ["GlobeValve-1"]})
    assert [p.get("relief_devices") for p in left.paths] == [["SpringLoadedGlobeSafetyValve-1"]]
    # the two sides of an exchanger stay separate in every route
    assert tools.call("find_path", {"source_entity_id": "P4712", "target_entity_id": "GlobeValve-3", "all_paths": True}).status == "empty"


def test_default_find_path_and_traverse_are_unchanged(tools):
    result = tools.call("find_path", {"source_entity_id": "P4712", "target_entity_id": "T4750"})
    assert len(result.paths) == 1 and result.meta["shortest_path_only"] is True and "blocked" not in result.meta


# ================================================================== instrumentation chain
@pytest.mark.parametrize("member", ["PICSA4712.02", "PT4712.02", "PV4712.02", "GlobeValve-1", "BlindFlange-2"])
def test_a_loop_is_traced_from_any_of_its_members(tools, member):
    result = derived(tools, "trace_instrumentation", entity_id=member)
    chain = next(row for row in result.derived if row["predicate"] == "signal_chain")
    assert chain["qualifiers"]["elements"] == ["BlindFlange-2", "ProcessSignalGeneratingFunction-2", "ProcessInstrumentationFunction-2", "ActuatingFunction-1", "GlobeValve-1"]
    assert chain["qualifiers"]["fail_action"] == "fail close"
    acts = next(row for row in result.derived if row["predicate"] == "loop_acts_on")
    assert (acts["subject"], acts["object"], acts["qualifiers"]["line"]) == ("ProcessInstrumentationFunction-2", "GlobeValve-1", "47127")
    assert {c["connection_type"] for c in result.connections} == {"sensing_location", "measuring_line", "signal_line", "operated_valve_reference"}


def test_a_loop_does_not_run_into_another_loop_through_a_shared_item(tools):
    tank = derived(tools, "trace_instrumentation", entity_id="T4750")  # the tank is where TT4750.03 measures
    assert "ProcessInstrumentationFunction-2" not in tank.meta["members"] and "GlobeValve-3" in tank.meta["members"]
    assert tools.call("trace_instrumentation", {"entity_id": "P4711"}).status == "empty"


def test_a_missing_fail_action_is_said_to_be_missing():
    tools = GraphTools(GraphService.from_file(EXAMPLES / "I05V01-VER.EX01.xml"))
    result = derived(tools, "trace_instrumentation", entity_id="GlobeValve-1")
    acts = [row for row in result.derived if row["predicate"] == "loop_acts_on"]
    assert len(acts) == 4 and all("no fail action is encoded" in row["statement"] and "fail_action" not in row["qualifiers"] for row in acts)


# ================================================================== a line and its branches
def test_a_line_is_returned_as_runs_between_junctions(tools):
    result = derived(tools, "trace_line", line="47126")
    runs = {(row["subject"], row["object"]): row["qualifiers"] for row in result.derived if row["predicate"] == "line_run"}
    assert len(runs) == 10
    assert runs[("PipeTee-3", "BlindFlange-1")]["components"] == ["BallValve-3"] and runs[("PipeTee-3", "BlindFlange-1")]["diameters"] == ["DN 25"]
    assert runs[("PipeTee-5", "FlowOutPipeOffPageConnector-1")]["ends_at"] == "the piping leaves the drawing here"
    assert runs[("PipeTee-2", "BallValve-2")]["ends_at"] == "end of the drawn piping"
    other = {(row["subject"], row["value"]) for row in result.derived if row["predicate"] == "line_meets_line"}
    assert ("PipeTee-1", "47125") in other
    assert tools.call("trace_line", {"line": "line 47126"}).meta["runs"] == 10
    missing = tools.call("trace_line", {"line": "99999"})
    assert missing.status == "not_found" and "47126" in missing.meta["lines"]


def test_a_size_change_inside_a_run_is_kept_in_order():
    tools = GraphTools(GraphService.from_file(EXAMPLES / "C02V03-VER.EX02.xml"))
    run = next(row for row in derived(tools, "trace_line", line="2750.001.6").derived if row["predicate"] == "line_run")
    assert run["qualifiers"]["components"] == ["PipeReducer-1"] and run["qualifiers"]["diameters"] == ["DN 200", "DN 150"]


def test_the_analyses_run_on_every_official_example():
    for path in sorted(EXAMPLES.glob("*.xml")):
        service = GraphService.from_file(path)
        tools = GraphTools(service)
        for entity in service.index.entities.values():
            if entity.in_topology and service.piping.degree(entity.id):
                assert tools.call("isolation_boundary", {"entity_id": entity.id}).status == "success", (path.name, entity.id)
            if entity.category == "instrumentation":
                assert tools.call("trace_instrumentation", {"entity_id": entity.id}).status in ("success", "empty"), (path.name, entity.id)
        for line in {str(c.properties["lineNumber"]) for c in service.index.connections.values() if c.relationship == "piping" and c.properties.get("lineNumber")}:
            assert tools.call("trace_line", {"line": line}).status == "success", (path.name, line)


# ================================================================== attributes and resolution
def test_listing_with_attributes_and_a_property_filter(tools):
    listed = tools.call("list_entities", {"entity_type": "ActuatingFunction", "properties": ["failAction"]})
    assert {e["id"]: e["attributes"][0]["value"] for e in listed.entities} == {"ActuatingFunction-1": "fail close", "ActuatingFunction-2": "fail close", "ActuatingFunction-3": "fail open"}
    # the value is carried by the actuator, a sub-object; the listing says so
    assert listed.entities[0]["attributes"][0] == {"property": "failAction", "value": "fail close", "on": "ControlledActuator-1"}
    for wanted in ("84 kW", "84.0 kW", "84kW", "84"):
        found = tools.call("list_entities", {"entity_type": "pump", "property_filter": {"designShaftPower": wanted}})
        assert [e["id"] for e in found.entities] == ["ReciprocatingPump-1"], wanted
    assert tools.call("list_entities", {"entity_type": "pump", "property_filter": {"designShaftPower": "84 bar"}}).status == "empty"
    assert same_value("DN 50", "dn50") and not same_value("DN 50", "DN 80") and not same_value("84.0 kW", "84 m")


def test_an_abbreviation_resolves_only_when_one_type_word_starts_with_it(tools):
    def ids(query):
        result = tools.call("find_entities", {"query": query})
        return result.status, [e["id"] for e in result.entities]

    assert ids("recip pump") == ("success", ["ReciprocatingPump-1"]) and ids("centrif pump") == ("success", ["CentrifugalPump-1"])
    assert ids("plate exchanger") == ("success", ["PlateHeatExchanger-1"]) and ids("tubular exchanger") == ("success", ["TubularHeatExchanger-1"])
    assert ids("the pump")[0] == "ambiguous" and ids("rec pump")[0] == "ambiguous"  # too short to be an abbreviation
    other = GraphTools(GraphService.from_file(EXAMPLES / "C03V04-VER.EX02.xml"))  # words that are not in the follow-up examples
    assert [e["id"] for e in other.call("find_entities", {"query": "restr orifice"}).entities] == ["RestrictionOrifice-1"]
    assert [e["id"] for e in other.call("find_entities", {"query": "orif"}).entities] == ["RestrictionOrifice-1"]
    source = (ROOT / "src" / "pid_agent" / "graph" / "entity_resolver.py").read_text().casefold()
    code = source.replace('("recip" -> "reciprocating")', "")  # the docstring example is not a table entry
    assert "recip" not in code and "centrif" not in code and "84" not in code


# ================================================================== structured answers
BOUNDARY = [call("isolation_boundary", entity_id="T4750")]
ORDER = {"category": "operating_procedure", "note": "The order in which to close the valves is not in the P&ID."}


def ask(tools, question, *turns, mode="structured"):
    agent = PidAgent(llm := ScriptedLLM(*turns), tools, answer_mode=mode)
    result = agent.ask(question, question_id="t")
    return result, llm, agent


def test_a_structured_answer_is_written_by_the_application_from_the_cited_rows(tools):
    result, llm, _ = ask(tools, "Which valves isolate T4750, in which order?", BOUNDARY, [call("submit_answer", derived_facts=["R1"], unknowns=[ORDER])])
    assert result.grounding_status == "grounded" and result.answer_mode == "structured"
    assert "Derived by graph analysis of the drawing" in result.answer and "GlobeValve 47123/C1 (GlobeValve-2) is the nearest valve" in result.answer
    assert "Not established by the P&ID" in result.answer and "A P&ID does not contain operating procedures or sequences" in result.answer
    assert all(item["operation"] == "isolation_boundary" for item in result.submission["derived_facts"]) and not result.submission["direct_facts"]
    assert [t["name"] for t in llm.calls[0]["tools"]] == ["decompose_request"] and llm.calls[0]["tool_choice"] == "required"
    assert [s.status for s in result.trace if s.tool == "submit_answer"] == ["accepted"]
    transcript = workflow.format_transcript(result)
    assert "submit_answer   (final answer, checked by the application)" in transcript and "<- isolation_boundary_valve(Tank-1, GlobeValve-2)" in transcript


def test_direct_and_derived_are_decided_by_the_tool_result_not_by_the_model(tools):
    turns = ([call("get_properties", ids=["P4712"], requested_properties=["designShaftPower"])], [call("traverse", start_entity_id="P4712", direction="downstream", entity_types=["equipment"])],
             [call("submit_answer", direct_facts=["R2"], derived_facts=["E1.1"])])
    result, _, _ = ask(tools, "q", *turns)
    assert [i["ref"] for i in result.submission["direct_facts"]] == ["E1.1"]
    assert {i["operation"] for i in result.submission["derived_facts"]} == {"traverse"}
    assert any("decided by the tool result" in note for note in result.submission["notes"])
    assert {"p": "has_property", "s": "ReciprocatingPump-1", "v": "84.0 kW", "q": {"property": "designShaftPower"}} in result.submission["direct_facts"][0]["facts"]


def test_an_id_that_no_result_contains_is_rejected_and_can_be_corrected(tools):
    result, llm, _ = ask(tools, "q", BOUNDARY, [call("submit_answer", derived_facts=["R1", "E9.9"])], [call("submit_answer", derived_facts=["R1"])])
    assert [s.status for s in result.trace if s.tool == "submit_answer"] == ["rejected", "accepted"] and result.grounding_status == "grounded"
    assert "E9.9" in llm.tool_messages()[-1]["problems"][0]


def test_an_answer_that_never_validates_is_withheld(tools):
    bad = [call("submit_answer", derived_facts=["E9.9"])]
    result, _, _ = ask(tools, "q", BOUNDARY, bad, bad, bad)
    assert result.grounding_status == "fallback" and result.submission is None
    assert "could not be validated" in result.answer and "What the graph tools returned" in result.answer


def test_prose_is_not_an_answer_in_structured_mode(tools):
    result, llm, _ = ask(tools, "q", BOUNDARY, "T4750 is isolated by closing XV-1 first.", [call("submit_answer", derived_facts=["R1"])])
    assert result.grounding_status == "grounded" and "XV-1" not in result.answer
    assert any(s.tool == "(answer written as text)" for s in result.trace)
    assert "submit_answer" in llm.calls[-1]["messages"][-1]["content"] or llm.calls[-1]["messages"][-2]["role"] in ("user", "assistant")


SEQUENCE = "Close the two upstream valves first, then the downstream one. This order allows safe depressurization."


def test_no_text_written_by_the_model_reaches_the_answer(tools):
    turns = (BOUNDARY, [call("submit_answer", derived_facts=["R1"], summary=SEQUENCE, unknowns=[{"category": "operating_procedure", "about": ["T4750"], "note": SEQUENCE}])])
    result, _, _ = ask(tools, "Which valves isolate T4750, and in which order?", *turns)
    assert result.grounding_status == "grounded"
    for words in ("valves first", "depressurization", "safe", "then the downstream", "order allows"):
        assert words not in result.answer, words
    # what the user reads about the unknown is the category's fixed statement and the item it concerns
    assert "- A P&ID does not contain operating procedures or sequences, such as the order in which to operate valves. Asked about: T4750 (Tank-1)." in result.answer
    assert result.submission["model_summary"] == SEQUENCE and result.submission["unknowns"][0]["note"] == SEQUENCE  # kept for the log only
    assert set(result.answer.split("\n\n")[0].splitlines()[0:1]) == {"Derived by graph analysis of the drawing"}
    lines = [line for line in result.answer.splitlines() if line.startswith("- ")]
    rows = {item["text"] for item in result.submission["derived_facts"]}
    assert all(line[2:].rsplit(" [", 1)[0] in rows or line.startswith("- A P&ID does not") for line in lines)


@pytest.mark.parametrize(
    ("category", "words"),
    [("operating_procedure", "operating procedures or sequences"), ("process_behaviour", "how pressure, flow, level or temperature would respond"),
     ("off_drawing", "beyond an off-page connector or an open-ended pipe"), ("not_represented", "does not contain an item or attribute"), ("design_adequacy", "adequate or safe")],
)
def test_each_kind_of_unknown_is_stated_by_the_application(tools, category, words):
    """A requested output the drawing cannot support is named by category; the wording is fixed."""
    observations = [annotate_refs(tools.call("isolation_boundary", {"entity_id": "T4750"}).to_dict(), 1)]
    answer = validate_submission({"derived_facts": ["R1"], "unknowns": [{"category": category, "note": "anything at all"}]}, observations)
    assert answer.ok and words in answer.render() and "anything at all" not in answer.render()


def test_the_contract_asks_for_an_unknown_for_every_unsupported_part_of_a_request():
    assert "For every requested conclusion or output component that cannot be supported by a direct fact or a deterministic derived fact, add a typed unknown" in " ".join(STRUCTURED_SYSTEM_PROMPT.split())
    assert "Nothing you write as text is shown to the user" in " ".join(STRUCTURED_SYSTEM_PROMPT.split())
    path = next(t for t in tool_specs() if t["name"] == "find_path")["description"]
    assert "only the shortest route is returned" in path and "Use all_paths when the question is about alternatives" in path


def test_unknowns_about_accepts_ids_tags_and_names_that_resolve_to_one_item(tools):
    observations = [annotate_refs(tools.call("isolation_boundary", {"entity_id": "T4750"}).to_dict(), 1)]

    def about(*items):
        return validate_submission({"derived_facts": ["R1"], "unknowns": [{"category": "off_drawing", "about": list(items)}]}, observations, tools.resolve_entity)

    for text in ("Tank-1", "T4750", "t-4750", "SV 104.01", "sv104.01", "the tank"):  # id, tag, normalized tag, position number, a type that names one item
        answer = about(text)
        assert answer.ok and len(answer.unknowns[0]["about"]) == 1, text
    assert about("SV 104.01").unknowns[0]["about"] == ["SpringLoadedGlobeSafetyValve-1"] and "SV 104.01 (SpringLoadedGlobeSafetyValve-1)" in about("SV 104.01").render()
    several = about("the pump")
    assert not several.ok and "matches several items (CentrifugalPump-1, ReciprocatingPump-1)" in several.errors[0]  # never picked silently
    nothing = about("pressure controller on the discharge")
    assert not nothing.ok and "does not name an item in the drawing" in nothing.errors[0]
    assert not about("Pump-99").ok


def test_submission_schema(tools):
    observations = [annotate_refs(tools.call("isolation_boundary", {"entity_id": "T4750"}).to_dict(), 1)]
    assert not validate_submission({}, observations).ok  # nothing cited and nothing declared unknown
    assert not validate_submission({"derived_facts": ["R1"], "unknowns": [{"category": "guesswork"}]}, observations).ok
    assert not validate_submission({"derived_facts": ["R1"], "commentary": ["free text"]}, observations).ok  # there is no free-text field to show
    assert validate_submission({"unknowns": [{"category": "off_drawing", "about": ["Tank-1"]}]}, observations).ok
    assert set(submit_answer_spec()["parameters"]["properties"]) == {"direct_facts", "derived_facts", "unknowns", "summary"}


# ---- what was asked, and whether all of it was accounted for
ASKED = [call("decompose_request", requested_outputs=[{"description": "which pumps there are", "kind": "items"}, {"description": "the design shaft power of each", "kind": "property"},
                                                      {"description": "which one should be serviced first", "kind": "ordering_or_procedure"}])]
PUMPS = [call("list_entities", entity_type="pump", properties=["designShaftPower"])]
QUESTION = "Which pumps are there, what is the shaft power of each, and which should be serviced first?"


def covered(*covers, unknown=None):
    return call("submit_answer", direct_facts=[{"ref": "R2", "covers": list(covers)}], unknowns=[unknown] if unknown else [])


def test_the_request_is_decomposed_first_and_ids_come_from_code(tools):
    result, llm, _ = ask(tools, QUESTION, ASKED, PUMPS, [covered("q1", "q2", unknown={"category": "operating_procedure", "covers": ["q3"]})])
    assert [(o["id"], o["kind"]) for o in result.requested_outputs] == [("q1", "items"), ("q2", "property"), ("q3", "ordering_or_procedure")]
    assert result.grounding_status == "grounded" and result.iterations == 2  # recording what was asked is not a planning step
    shown = llm.calls[1]["messages"][-1]["content"]
    assert '"id": "q3"' in shown and "every one of these ids must be covered" in shown
    by = {o["id"]: o["covered_by"] for o in result.submission["requested_outputs"]}
    assert by["q1"]["direct"] and by["q2"]["direct"] and by["q3"] == {"direct": [], "derived": [], "unknown": ["operating_procedure"]}
    assert "which one should be serviced first" not in result.answer  # the model's paraphrase of the question is not answer text
    assert "A P&ID does not contain operating procedures or sequences" in result.answer


def test_a_requested_output_that_is_passed_over_is_rejected_until_it_is_accounted_for(tools):
    result, llm, _ = ask(tools, QUESTION, ASKED, PUMPS, [covered("q1", "q2")], [covered("q1", "q2", unknown={"category": "operating_procedure", "covers": ["q3"]})])
    problems = next(s.result["problems"] for s in result.trace if s.tool == "submit_answer" and s.status == "rejected")
    assert problems == ["Requested output q3 (which one should be serviced first) has not been addressed. Provide supported evidence or mark it unknown."]
    assert [s.status for s in result.trace if s.tool == "submit_answer"] == ["rejected", "accepted"] and result.grounding_status == "grounded"
    stray, _, _ = ask(tools, QUESTION, ASKED, PUMPS, [covered("q1", "q2", "q3", "q9")], [covered("q1", "q2", "q3")])
    assert "q9, which is not a requested output" in next(s.result["problems"] for s in stray.trace if s.status == "rejected")[0]


@pytest.mark.parametrize(
    ("outputs", "question"),
    [(["where the measurement is taken", "what it actuates", "the fail position", "the line"], "Where is the measurement taken, what does it actuate, what is its fail position, and which line is it on?"),
     (["how many there are", "where each is", "their properties"], "How many are there, where are they, and what properties do they have?")],
)
def test_coverage_is_about_the_request_not_about_any_particular_question(tools, outputs, question):
    asked = [call("decompose_request", requested_outputs=[{"description": d} for d in outputs])]
    ids = [f"q{i}" for i in range(1, len(outputs) + 1)]
    partial, _, _ = ask(tools, question, asked, PUMPS, [covered(*ids[:-1])], [covered(*ids)])
    rejected = next(s.result["problems"] for s in partial.trace if s.status == "rejected")
    assert rejected == [f"Requested output {ids[-1]} ({outputs[-1]}) has not been addressed. Provide supported evidence or mark it unknown."]


def test_decomposition_details(tools):
    single = [call("decompose_request", requested_outputs=[{"description": "the pumps"}])]
    result, _, _ = ask(tools, "pumps?", single, PUMPS, [call("submit_answer", direct_facts=["R2"])])  # one thing asked: bare ids are enough
    assert result.grounding_status == "grounded" and result.submission["requested_outputs"][0]["covered_by"] is not None
    bad, llm, _ = ask(tools, "q", [call("decompose_request", requested_outputs=[])], single, PUMPS, [call("submit_answer", direct_facts=["R3"])])
    assert [s.status for s in bad.trace if s.tool == "decompose_request"] == ["rejected", "accepted"] and bad.grounding_status == "grounded"
    assert [t["name"] for t in llm.calls[1]["tools"]] == ["decompose_request"] and len(llm.calls[2]["tools"]) == 11
    spec = workflow.decompose_request_spec()
    text = json.dumps(spec).casefold()
    assert "do not judge whether the drawing can answer it" in text
    for tool in ("isolation_boundary", "trace_instrumentation", "trace_line", "find_path", "traverse"):  # no request -> tool routing
        assert tool not in text and tool not in STRUCTURED_SYSTEM_PROMPT.split("Final answer")[0].split("What was asked")[1]


# ---- one repair of a rejected final submission (the boundary is step 2, after the decomposition)
FORCED = AgentLimits(max_iterations=1)
GOOD = [call("submit_answer", derived_facts=["R2"])]


def forced(tools, *turns):
    one = [call("decompose_request", requested_outputs=[{"description": "the boundary"}])]
    agent = PidAgent(llm := ScriptedLLM(one, BOUNDARY, *turns), tools, limits=FORCED, answer_mode="structured")
    return agent.ask("q", question_id="t"), llm, agent


@pytest.mark.parametrize(
    ("broken", "problem"),
    [([call("submit_answer", derived_facts=["R2"], unknowns=[{"category": "operating_state", "about": ["valve"]}])], "matches several items"),
     ([call("submit_answer", derived_facts=["R2", "E7.7"])], "'E7.7' is not an evidence id"),
     ([call("submit_answer", derived_facts=["R2"], unknowns=[{"category": "made_up"}])], "Invalid submit_answer arguments"),
     ("The valves are closed in sequence.", "did not call submit_answer")],
)
def test_a_rejected_final_submission_gets_exactly_one_repair(tools, broken, problem):
    result, llm, agent = forced(tools, broken, GOOD)
    assert result.grounding_status == "grounded" and result.repair["attempted"] and result.repair["succeeded"]
    assert problem in result.repair["initial_problems"][0]
    assert [s.status for s in result.trace if s.tool == "submit_answer"] == ["rejected", "accepted"]
    repair_call = llm.calls[-1]
    assert [t["name"] for t in repair_call["tools"]] == ["submit_answer"] and repair_call["tool_choice"] == "required"
    assert problem in json.dumps([m["content"] for m in repair_call["messages"][-2:]]) and "last attempt" in repair_call["messages"][-1]["content"]
    assert len(agent.last_observations) == 1 and len(llm.calls) == 4  # decompose, one graph call, the rejected answer, the repair


def test_a_repair_that_is_still_invalid_ends_the_run(tools):
    bad = [call("submit_answer", derived_facts=["E7.7"])]
    result, llm, _ = forced(tools, bad, bad, GOOD)
    assert result.grounding_status == "fallback" and result.repair == {"initial_problems": result.repair["initial_problems"], "attempted": True, "succeeded": False}
    assert len(llm.calls) == 4 and [s.status for s in result.trace if s.tool == "submit_answer"] == ["rejected", "rejected"]  # no third try


def test_no_graph_call_is_possible_during_the_repair(tools):
    result, llm, agent = forced(tools, [call("submit_answer", derived_facts=["E7.7"])], [call("isolation_boundary", entity_id="P4712")], GOOD)
    assert result.grounding_status == "fallback" and not result.repair["succeeded"]
    assert len(agent.last_observations) == 1 and [s.tool for s in result.trace if s.executed] == ["isolation_boundary"]  # only the call made before
    assert len(llm.calls) == 4


def test_an_accepted_final_submission_needs_no_repair(tools):
    result, llm, _ = forced(tools, GOOD)
    assert result.grounding_status == "grounded" and result.repair is None and len(llm.calls) == 3


def test_the_status_of_an_empty_result_can_be_cited(tools):
    result, _, _ = ask(tools, "q", [call("get_connections", entity_id="P4711", relationship="instrumentation")], [call("submit_answer", direct_facts=["E1.0"])])
    assert result.grounding_status == "grounded" and "no instrumentation connections" in result.answer


def test_the_structured_path_does_not_use_the_prose_validator(tools, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the sentence-level validator must not run for a structured answer")

    monkeypatch.setattr(workflow, "check_answer", forbidden)
    result, _, _ = ask(tools, "q", BOUNDARY, [call("submit_answer", derived_facts=["R1"], unknowns=[ORDER])])
    assert result.grounding_status == "grounded"


def test_prompt_and_tools_contain_nothing_from_the_follow_up_examples():
    text = (STRUCTURED_SYSTEM_PROMPT + json.dumps(tool_specs()) + json.dumps(submit_answer_spec())).casefold()
    for term in ("t4750", "p4712", "p4711", "h1007", "h1008", "picsa", "hs4750", "hv4750", "pi4712", "47126", "47123", "84 kw", "recip", "blocked in", "trip", "maintenance", "plate exchanger"):
        assert term not in text, term
    for group in GROUPS:
        for phrasing in group["phrasings"]:
            assert phrasing["question"].casefold() not in text
    for path in (ROOT / "src").rglob("*.py"):
        source = path.read_text()
        assert not any(q["question"] in source for q in QUESTIONS), path.name


# ================================================================== gold
def test_every_gold_fact_is_produced_by_a_graph_operation(tools):
    for item in [*QUESTIONS, *GROUPS]:
        primary = followup.gold_facts(tools, item["gold_calls"])
        wider = followup.gold_facts(tools, [*item["gold_calls"], *item["alt_calls"]])
        for required in item["required"]:
            assert "any_of" in required or required["unknown"], (item["id"], required)
            patterns = required.get("any_of", [])
            if patterns:
                assert any(followup.matches(p, f) for p in patterns for f in primary), (item["id"], required["fact"])
            for pattern in patterns:  # every accepted form is a real fact, not a guess
                assert any(followup.matches(pattern, f) for f in wider), (item["id"], required["fact"], pattern)
        assert all(tools.call("get_entity", {"entity_id": a}).status == "success" for a in item["anchors"]), item["id"]
    for group in GROUPS:  # a phrasing with its own gold is checked the same way
        for phrasing in group["phrasings"]:
            for required in phrasing.get("required", []):
                facts = followup.gold_facts(tools, [*group["gold_calls"], *group["alt_calls"]])
                assert all(any(followup.matches(p, f) for f in facts) for p in required["any_of"]), (phrasing["id"], required["fact"])


def test_the_suites_meet_the_brief():
    provided = [q for q in QUESTIONS if q["source"] == "provided"]
    own = [q for q in QUESTIONS if q["source"] == "own"]
    assert [q["id"] for q in provided] == [f"C{i}" for i in range(1, 16)] and len(own) >= 10
    assert [g["id"] for g in GROUPS if g["source"] == "provided"] == ["R1", "R2", "R3", "R4"]
    mine = [g for g in GROUPS if g["source"] == "own"]
    assert len(mine) >= 5 and all(len(g["phrasings"]) >= 4 for g in GROUPS) and sum(g["complex"] for g in mine) >= 2
    # where the drawing is silent the gold asks for an unknown, never for an invented answer
    by_id = {q["id"]: q for q in QUESTIONS}
    assert {"unknown": ["operating_procedure"]} in by_id["C1"]["required"] and {"unknown": ["process_behaviour"]} in by_id["C5"]["required"]


def test_tool_names_lose_only_leaked_protocol_tokens(tools):
    from pid_agent.llm.base import ToolCall, clean_tool_name

    assert clean_tool_name("submit_answer") == "submit_answer"
    assert clean_tool_name("submit_answer<|channel|>commentary") == "submit_answer" and clean_tool_name("get_connections<|constrain|>json") == "get_connections"
    assert clean_tool_name("submit_answers") == "submit_answers" and clean_tool_name("run_shell<|channel|>commentary") == "run_shell"  # nothing is guessed
    leaked = ToolCall.from_raw("c1", "isolation_boundary<|channel|>commentary", '{"entity_id": "T4750"}')
    assert leaked.name == "isolation_boundary" and tools.call(leaked.name, leaked.arguments).status == "success"
    unknown = ToolCall.from_raw("c2", "run_shell<|channel|>commentary", "{}")
    assert tools.call(unknown.name, unknown.arguments).status == "error" and tools.call("submit_answers", {}).status == "error"
    result, _, _ = ask(tools, "q", BOUNDARY, [ToolCall.from_raw("c3", "submit_answer<|channel|>commentary", '{"derived_facts": ["R1"]}')])
    assert result.grounding_status == "grounded"


def test_pattern_matching():
    path = {"p": "path", "s": "A", "o": "B", "q": {"entities": ["A", "V", "B"], "direction": "downstream", "blocked": ["X"]}}
    assert followup.matches({"p": "path", "ends": ["B", "A"], "contains": ["V"], "blocked_contains": "X"}, path)
    assert not followup.matches({"p": "path", "blocked_absent": True}, path) and not followup.matches({"p": "path", "contains": ["W"]}, path)
    nozzle = {"p": "has_property", "s": "Nozzle-7", "v": "N1", "q": {"property": "subTagName", "owner": "Pump-1"}}
    assert followup.matches({"p": "has_property", "s": "Pump-1", "q": {"property": "subTagName"}}, nozzle) and followup.matches({"s": "Nozzle-7"}, nozzle) and not followup.matches({"s": "Pump-2"}, nozzle)
    value = {"p": "has_property", "s": "P", "v": "84.0 kW", "q": {"property": "designShaftPower"}}
    assert followup.matches({"p": ["has_property"], "s": "P", "v": "84 kW", "q": {"property": "designShaftPower"}}, value)
    assert not followup.matches({"p": "has_property", "v": "85 kW"}, value)
    assert followup.matches({"p": "fully_valve_bounded", "v": False}, {"p": "fully_valve_bounded", "s": "E", "v": False})


# ================================================================== scoring and consistency
def run_record(tools, item, turns, repeat=1, group=None):
    result, _, agent = ask(tools, item["question"], *turns)
    return {**result.to_dict(), "question_id": item["id"], "tool_results": agent.last_observations, "repeat": repeat, "group": group}


def test_complex_scoring_counts_facts_and_unknowns_separately(tools):
    c1 = next(q for q in QUESTIONS if q["id"] == "C1")
    full = run_record(tools, c1, [BOUNDARY, [call("submit_answer", derived_facts=["R1"], unknowns=[ORDER])]])
    no_unknown = run_record(tools, c1, [BOUNDARY, [call("submit_answer", derived_facts=["R1"])]])
    invented = run_record(tools, c1, [BOUNDARY, [call("submit_answer", derived_facts=["E9.9"])]])
    assert followup.judge(c1, full)["outcome"] == "correct" and followup.judge(c1, full)["score"] == 1.0
    partial = followup.judge(c1, no_unknown)
    assert partial["outcome"] == "partial" and partial["score"] == 0.8 and [r["item"] for r in partial["required"] if not r["found"]] == ["unknown: operating_procedure"]
    assert followup.judge(c1, invented)["outcome"] == "withheld" and followup.judge(c1, invented)["score"] == 0.0
    assert followup.cause(c1, no_unknown, partial) == "answer synthesis" and followup.cause(c1, invented, followup.judge(c1, invented)) == "grounding rejection"
    report = followup.report_complex(QUESTIONS, {"provider": "p", "model": "m", "commit": "c", "dirty": False, "run_id": "r", "results": [full]})
    assert report["outcomes"] == {"correct": 1} and report["required_unknowns"] == {"named": 1, "of": 1} and report["grounding"]["unsupported_facts_in_answers"] == 0


def test_consistency_is_judged_on_facts_not_on_wording(tools):
    group = next(g for g in GROUPS if g["id"] == "R1")
    a, b = group["phrasings"][0], group["phrasings"][1]
    boundary = [call("isolation_boundary", entity_id="P4712")]
    complete = [boundary, [call("submit_answer", derived_facts=["R1"])]]
    extra = [boundary, [call("get_properties", ids=["P4712"], requested_properties=["designShaftPower"])], [call("submit_answer", derived_facts=["R1"], direct_facts=["R2"])]]
    one_valve = [boundary, [call("submit_answer", derived_facts=["E1.2"])]]            # retrieved, not cited
    adjacency = [[call("get_connections", entity_id="P4712", relationship="piping")], [call("submit_answer", direct_facts=["R1"])]]  # a tool that cannot see the boundary
    wrong_pump = [[call("isolation_boundary", entity_id="P4711")], [call("submit_answer", derived_facts=["R1"])]]

    def report(*records):
        return followup.report_consistency(GROUPS, {"provider": "p", "model": "m", "commit": "c", "dirty": False, "run_id": "r", "repeats": 2, "results": list(records)})["group_rows"][0]

    same = report(run_record(tools, a, complete, 1), run_record(tools, a, extra, 2), run_record(tools, b, complete, 1), run_record(tools, b, complete, 2))
    # extra correct facts are not an inconsistency; the overlap of the full fact sets is only descriptive
    assert same["cross_phrasing_consistent"] and same["repeat_consistent_phrasings"] == 2 and same["required_fact_recall"] == 1.0 and same["jaccard_overlap"] < 1.0
    assert not same["contradictions"] and same["entity_resolution_consistent"] and all(r["cause"] is None for r in same["run_rows"])

    mixed = report(run_record(tools, a, complete, 1), run_record(tools, a, one_valve, 2), run_record(tools, b, adjacency, 1), run_record(tools, b, wrong_pump, 2))
    assert not mixed["cross_phrasing_consistent"] and mixed["repeat_consistent_phrasings"] == 0 and not mixed["entity_resolution_consistent"]
    assert [r["cause"] for r in mixed["run_rows"]] == [None, "answer synthesis", "planner/tool choice", "entity resolution"]


def test_contradictions_are_values_that_cannot_both_hold():
    one = [{"p": "has_property", "s": "P", "v": "84.0 kW", "q": {"property": "designShaftPower"}}, {"p": "loop_acts_on", "s": "C", "o": "V1"}]
    two = [{"p": "has_property", "s": "P", "v": "84.0 KW", "q": {"property": "designShaftPower"}}, {"p": "loop_acts_on", "s": "C", "o": "V2"}, {"p": "reaches", "s": "P", "o": "T"}]
    found = followup._contradictions([one, two])
    assert [(c["predicate"], c["subject"]) for c in found] == [("loop_acts_on", "C")]
    # a controller that the drawing shows acting on two valves is multi-valued, not contradictory
    assert followup._contradictions([one, two], [[{"p": "loop_acts_on", "s": "C", "o": "V1"}, {"p": "loop_acts_on", "s": "C", "o": "V2"}]]) == []
    wrong = followup._contradictions([[{"p": "has_property", "s": "P", "v": "84.0 kW", "q": {"property": "designShaftPower"}}], [{"p": "has_property", "s": "P", "v": "48.0 kW", "q": {"property": "designShaftPower"}}]])
    assert [(c["subject"], c["property"]) for c in wrong] == [("P", "designShaftPower")]


def test_sub_objects_of_one_item_are_not_one_property_slot(tools):
    """Two nozzles, or two chambers, of one item carry the same property with different values."""
    def cited(entity, *refs_from):
        observations = [annotate_refs(tools.call("get_entity", {"entity_id": entity, "include_children": True}).to_dict(), 1)]
        registry = EvidenceRegistry(observations)
        return [f for f in registry.all_facts() if f["p"] == "has_property"]

    pump, exchanger = cited("P4712"), cited("H1008")
    tags = [f for f in pump if f["q"]["property"] == "subTagName"]
    assert len({f["s"] for f in tags}) == len(tags) >= 2 and all(f["s"].startswith("Nozzle-") and f["q"]["owner"] == "ReciprocatingPump-1" for f in tags)
    chambers = [f for f in exchanger if f["s"].startswith("Chamber-")]
    assert len({f["s"] for f in chambers}) >= 2
    for facts in (pump, exchanger):
        halves = [facts[: len(facts) // 2], facts[len(facts) // 2 :]]
        assert followup._contradictions(halves) == [] and followup._contradictions([facts, facts]) == []
    # the same fact reads the same whichever tool returned it
    listed = EvidenceRegistry([annotate_refs(tools.call("list_entities", {"entity_type": "ActuatingFunction", "properties": ["failAction"]}).to_dict(), 1)]).all_facts()
    looked_up = EvidenceRegistry([annotate_refs(tools.call("get_properties", {"ids": ["ActuatingFunction-1"], "requested_properties": ["failAction"]}).to_dict(), 1)]).all_facts()
    fail = {"p": "has_property", "s": "ControlledActuator-1", "v": "fail close", "q": {"property": "failAction", "owner": "ActuatingFunction-1"}}
    assert fail in listed and fail in looked_up


def test_resolving_the_item_asked_about_is_judged_apart_from_reaching_the_answer(tools):
    group = next(g for g in GROUPS if g["id"] == "R3")
    assert group["anchors"] == ["ProcessInstrumentationFunction-2"]  # the controller the question names, not the valve of the answer
    a, d = group["phrasings"][0], group["phrasings"][3]
    links = [call("get_connections", entity_id="PICSA4712.02", relationship="instrumentation")]
    literal = run_record(tools, a, [links, [call("submit_answer", direct_facts=["R1"])]])            # the controller's own links, nothing further
    lost = run_record(tools, d, [[call("get_entity", entity_id="P4712")], [call("submit_answer", direct_facts=["R1"])]], repeat=1)  # never found the controller
    full = run_record(tools, d, [[call("trace_instrumentation", entity_id="PICSA4712.02")], [call("submit_answer", direct_facts=["R1"], derived_facts=["R1"])]], repeat=2)
    assert followup.anchors_resolved(group, literal) and not followup.anchors_resolved(group, lost) and followup.anchors_resolved(group, full)
    row = followup.report_consistency(GROUPS, {"provider": "p", "model": "m", "commit": "c", "dirty": False, "run_id": "r", "repeats": 2, "results": [literal, lost, full]})["group_rows"][0]
    by = {(r["phrasing"], r["repeat"]): r for r in row["run_rows"]}
    # found the controller, did not reach the valve: planning, not resolution
    assert by[("R3a", 1)]["cause"] == "planner/tool choice" and by[("R3a", 1)]["entities_resolved"] is True
    assert by[("R3d", 1)]["cause"] == "entity resolution" and by[("R3d", 2)]["cause"] is None
    # the literal reading of "map all connections for X" is a correct answer to that question,
    # while the group as a whole asks for more, so the group is still not consistent
    assert by[("R3a", 1)]["question_outcome"] == "correct" and by[("R3a", 1)]["outcome"] == "incorrect" and by[("R3a", 1)]["recall"] == 0.0
    assert not row["cross_phrasing_consistent"] and not row["contradictions"]


def test_registry_reads_results_by_their_own_step_number(tools):
    observations = [annotate_refs(tools.call("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"], "blocked_entity_ids": ["BallValve-4"]}).to_dict(), 4)]
    registry = EvidenceRegistry(observations)
    reach = next(f for f in registry.all_facts() if f["p"] == "reaches")
    assert reach["q"] == {"direction": "downstream", "blocked": ["BallValve-4"]} and registry.kind("E4.1") == "derived"
