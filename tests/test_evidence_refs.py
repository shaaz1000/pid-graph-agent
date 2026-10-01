"""Evidence references, relationship-aware grounding, truncation handling. No model, no network.

The answer cites evidence rows by id; code resolves the ids to typed facts and checks that what
each sentence says is associated in those facts, not merely present somewhere in the results.
"""

from __future__ import annotations

import json

import httpx
import pytest

from fakes import ScriptedLLM, call
from pid_agent.agent.claims import build_facts
from pid_agent.agent.compact import compact_result
from pid_agent.agent.evidence_refs import annotate_refs, check_answer, sentences_of
from pid_agent.agent.workflow import PidAgent, format_transcript
from pid_agent.config import Settings, load_settings
from pid_agent.errors import ConfigError
from pid_agent.llm import create_llm
from pid_agent.llm.base import LLMResponse, response_from_chat_completion


def observe(tools, *calls):
    """Full tool results with evidence ids, exactly as the agent keeps them (step 1, 2, ...)."""
    return [annotate_refs(tools.call(name, arguments).to_dict(), step) for step, (name, arguments) in enumerate(calls, start=1)]


def level(tools, text, *calls, question="q"):
    return check_answer(text, question, observe(tools, *calls)).level


def kinds(tools, text, *calls, question="q"):
    report = check_answer(text, question, observe(tools, *calls))
    return {p["kind"] for p in report.problems}, {g["kind"] for g in report.gaps}


def ref_of(result, section, **match):
    """The evidence id the application gave to one row of a result."""
    for row in result[section]:
        flat = json.dumps(row)
        if all(f'"{v}"' in flat for v in match.values()):
            return row["ref"]
    raise AssertionError(f"no row matching {match}")


P4711 = ("get_connections", {"entity_id": "P4711", "relationship": "piping"})
P4712 = ("get_connections", {"entity_id": "P4712", "relationship": "piping"})


# ================================================================== finish_reason / truncation
@pytest.mark.parametrize(("reason", "truncated"), [("stop", False), ("length", True), ("tool_calls", False), ("content_filter", False), (None, False)])
def test_finish_reason_is_preserved_and_only_length_means_truncated(reason, truncated):
    payload = {"choices": [{"message": {"content": "text"}, **({"finish_reason": reason} if reason else {})}], "usage": {}}
    response = response_from_chat_completion(payload)
    assert response.finish_reason == reason and response.truncated is truncated


def test_adapter_reports_a_cut_off_response_as_truncated_not_as_an_answer():
    from pid_agent.llm.nvidia_provider import BASE_URL, NvidiaProvider

    body = {"choices": [{"message": {"content": "", "reasoning_content": "thinking..."}, "finish_reason": "length"}], "usage": {"completion_tokens": 4096}}
    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    response = NvidiaProvider(api_key="dummy-test-credential", model="m", http_client=client).complete([{"role": "user", "content": "hi"}])
    assert response.truncated and "thinking" not in repr(response)


def cut(text):
    return LLMResponse(content=text, finish_reason="length")


def test_truncated_answer_is_never_parsed_and_a_shorter_one_is_requested(tools):
    lookup = [call("find_entities", query="P4711")]
    partial = "P4711 is CentrifugalPump-1 and it conn"
    result = PidAgent(llm := ScriptedLLM(lookup, cut(partial), "P4711 is CentrifugalPump-1. [E1.1]"), tools).ask("What is P4711?")
    assert result.answer == "P4711 is CentrifugalPump-1. [E1.1]" and result.grounding_level == "grounded"
    assert result.truncated_outputs == 1 and result.rejected_drafts == []  # not a "missing claims" rejection
    step = next(s for s in result.trace if s.status == "truncated")
    assert "finish_reason=length" in step.result["message"] and not step.executed
    assert "cut off" in llm.calls[-1]["messages"][-1]["content"]


def test_truncated_structured_block_is_not_mistaken_for_missing_claims(tools):
    lookup = [call("find_entities", query="P4711")]
    partial = 'P4711 is CentrifugalPump-1.\n\n```claims\n[{"predicate": "is_a", "subject": "Centrifu'
    result = PidAgent(ScriptedLLM(lookup, cut(partial), cut(partial), cut(partial)), tools).ask("What is P4711?")
    assert result.grounding_status == "fallback" and result.truncated_outputs >= 2
    assert "cut off" in result.answer or "usable answer" in result.answer
    assert "```" not in result.answer and "Centrifu" not in result.answer.split("What the graph tools returned")[0]
    assert all(c["kind"] != "missing_claims" for d in result.rejected_drafts for c in d["unsupported_claims"])


def test_truncated_rewrite_is_withheld_with_its_own_reason(tools):
    lookup = [call("find_entities", query="P4711")]
    result = PidAgent(ScriptedLLM(lookup, "P4711 is a PlateHeatExchanger. [E1.1]", cut("P4711 is Centri")), tools).ask("What is P4711?")
    assert result.grounding_status == "fallback" and result.failure_reason.startswith("answer_truncated")
    assert "cut off at its output limit" in result.answer and "Centri" not in result.answer.split("What the graph tools returned")[0]


def test_timeout_is_configurable_and_distinct_from_truncation(monkeypatch, tmp_path):
    empty = tmp_path / ".env"
    empty.write_text("")
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "dummy-test-credential")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    assert load_settings(empty).llm_timeout_seconds == 45 and create_llm(load_settings(empty))._http.timeout.read == 45
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS")
    assert create_llm(load_settings(empty))._http.timeout.read == 240  # the adapter's own default
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "never")
    with pytest.raises(ConfigError, match="LLM_TIMEOUT_SECONDS"):
        load_settings(empty)
    assert Settings().llm_timeout_seconds is None


# =========================================================================== evidence ids
def test_ids_are_assigned_by_code_deterministically_and_shown_to_the_model(tools):
    first, second = observe(tools, P4711, P4712), observe(tools, P4711, P4712)
    assert [c["ref"] for r in first for c in r["connections"]] == [c["ref"] for r in second for c in r["connections"]]
    assert first[0]["result_ref"] == "R1" and first[1]["result_ref"] == "R2" and first[1]["status_ref"] == "E2.0"
    assert first[0]["entities"][0]["ref"] == "E1.1" and {c["ref"] for c in first[0]["connections"]} == {"E1.2", "E1.3"}
    seen = compact_result(first[0])
    assert seen["result_ref"] == "R1" and [c["ref"] for c in seen["connections"]] == ["E1.2", "E1.3"]
    index = build_facts(first)
    assert {"R1", "R2", "E1.1", "E1.2", "E1.3"} <= index.known_refs()
    fact = next(f for f in index.by_ref("E1.3") if f.predicate == "flows_to")
    assert fact.source_graph == "conceptual_graph" and fact.evidence_id.startswith("PipingNetworkSegment")
    assert len(index.by_ref("R1")) > len(index.by_ref("E1.1")) > 0


def test_valid_row_and_result_references(tools):
    obs = observe(tools, P4711)
    row = ref_of(obs[0], "connections", id="PlateHeatExchanger-1")
    assert check_answer(f"P4711 feeds H1007 through line 47122, DN 80. [{row}]", "q", obs).level == "grounded"
    assert check_answer("P4711 feeds H1007 through line 47122, DN 80. [R1]", "q", obs).level == "grounded"
    report = check_answer(f"P4711 feeds H1007 through line 47122. [{row}]", "q", obs)
    statement = report.supported[0]
    assert statement["refs"] == [row] and statement["facts"] and all(row in f["refs"] or "R1" for f in statement["facts"])
    assert any(f["predicate"] == "flows_to" and f["source_graph"] == "conceptual_graph" for f in statement["facts"])


@pytest.mark.parametrize("bad", ["[E9.9]", "[R7]", "[E1.99]"])
def test_nonexistent_reference_is_rejected(tools, bad):
    problems, _ = kinds(tools, f"P4711 feeds H1007 through line 47122. {bad}", P4711)
    assert "bad_reference" in problems


@pytest.mark.parametrize("bad", ["[E1]", "[E1.x]", "[E1.1 - E1.4]", "[ref 3]", "[evidence: step 1]"])
def test_malformed_reference_is_rejected(tools, bad):
    problems, _ = kinds(tools, f"P4711 feeds H1007 through line 47122. {bad}", P4711)
    assert "bad_reference" in problems


def test_duplicate_and_trailing_references_are_harmless(tools):
    assert level(tools, "P4711 feeds H1007 through line 47122 [E1.3, E1.3]. It is DN 80. [E1.3]", P4711) == "grounded"
    assert sentences_of("A feeds B. [E1.3] Next one. [E1.1, R2]") == ["A feeds B [E1.3].", "Next one [E1.1, R2]."]


def test_a_citation_on_its_own_line_covers_the_list_above_it(tools):
    """Seen in a live run: a bulleted list followed by one reference line."""
    obs, names = enumeration(tools, "H1007", ["valve"])
    listed = "\n".join(f"- {name}" for name in names)
    report = check_answer(f"The valves downstream of H1007 are:\n{listed}\n[R1]", "q", obs)
    assert report.level == "grounded" and not report.gaps
    # it does not reach back past a sentence that has its own reference
    mixed = check_answer(f"H1007 is PlateHeatExchanger-1. [E1.1]\n- {names[0]}\n[R1]\n- V-9001", "q", obs)
    assert any(p["claim"] == "V-9001" for p in mixed.problems)


def test_a_sentence_without_references_is_at_most_limited(tools):
    assert level(tools, "P4711 feeds H1007 through line 47122, DN 80.", P4711) == "limited"
    assert level(tools, "P4711 feeds H1007. [E1.3] The line is 47122, DN 80.", P4711) == "limited"


# ============================================================== enumeration at several sizes
def enumeration(tools, start, types, direction="downstream"):
    obs = observe(tools, ("traverse", {"start_entity_id": start, "direction": direction, **({"entity_types": types} if types else {})}))
    names = [e["name"] for e in obs[0]["entities"]]
    return obs, names


@pytest.mark.parametrize(("start", "types", "minimum"), [("H1007", ["tank"], 1), ("Tank-1", ["equipment"], 2), ("H1007", ["valve"], 10), ("P4711", None, 20)])
def test_one_result_reference_grounds_an_enumeration_of_any_size(tools, start, types, minimum):
    obs, names = enumeration(tools, start, types)
    assert len(names) >= minimum
    text = f"Downstream of {start}: {', '.join(names)}. [R1]"
    report = check_answer(text, "q", obs)
    assert report.level == "grounded", (report.problems, report.gaps)
    # the answer's evidence part does not grow with the result: one id, no restated facts
    assert text.count("[") == 1 and len(text) < 60 + sum(len(n) + 2 for n in names)


def test_largest_real_result_set_and_an_extra_item_slipped_into_it(tools):
    obs, names = enumeration(tools, "P4711", None)
    assert len(names) >= 20  # everything the drawing shows downstream of the first pump
    assert check_answer(f"Downstream of P4711: {', '.join(names)}. [R1]", "q", obs).level == "grounded"
    report = check_answer(f"Downstream of P4711: {', '.join(names)}, V-9001. [R1]", "q", obs)
    assert report.level == "insufficient_evidence" and any(p["claim"] == "V-9001" for p in report.problems)
    # a real valve that this traversal did not reach (the other side of the exchanger) is not covered either
    other = observe(tools, ("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["valve"]}), ("find_entities", {"query": "47141/C1"}))
    listed = ", ".join(e["name"] for e in other[0]["entities"])
    assert check_answer(f"Downstream of P4712: {listed}. [R1]", "q", other).level == "grounded"
    assert check_answer(f"Downstream of P4712: {listed}, GlobeValve-3. [R1]", "q", other).level != "grounded"


# ================================================================== relationship grounding
def test_correct_entity_property_and_wrong_pairing(tools):
    calls = (("get_properties", {"ids": ["P4711"], "requested_properties": ["designShaftPower"]}), ("get_properties", {"ids": ["P4712"], "requested_properties": ["designShaftPower"]}))
    obs = observe(tools, *calls)
    one, two = obs[0]["properties"]["CentrifugalPump-1"]["found"][0], obs[1]["properties"]["ReciprocatingPump-1"]["found"][0]
    assert one["value"] != two["value"]
    assert check_answer(f"P4711 has designShaftPower {one['value']}. [{one['ref']}]", "q", obs).level == "grounded"
    # both the tag and the value are in the evidence, but they do not belong together
    for refs in (f"[{one['ref']}]", f"[{two['ref']}]", "[R1, R2]", ""):
        report = check_answer(f"P4712 has designShaftPower {one['value']}. {refs}", "q", obs)
        assert report.level == "insufficient_evidence" and any(p["kind"] == "pairing" for p in report.problems), refs


def test_line_property_pairing_dn_80_does_not_move_to_another_line(tools):
    obs = observe(tools, P4711, P4712)
    dn80 = ref_of(obs[0], "connections", id="PlateHeatExchanger-1")
    assert check_answer(f"The line from P4711 to H1007 is DN 80. [{dn80}]", "q", obs).level == "grounded"
    assert check_answer("The line from P4712 to PipeTee-2 is DN 50. [R2]", "q", obs).level == "grounded"
    for refs in ("[R2]", "[R1, R2]", f"[{dn80}]", ""):
        report = check_answer(f"P4712's line is DN 80. {refs}", "q", obs)
        assert any(p["kind"] == "pairing" for p in report.problems), (refs, report.problems, report.gaps)
    report = check_answer("P4712's line is line 47122. [R1, R2]", "q", obs)
    assert any(p["kind"] == "pairing" for p in report.problems)


def test_correct_and_invented_relationship_between_two_items(tools):
    obs = observe(tools, P4711, ("find_entities", {"query": "T4750"}))
    assert check_answer("P4711 is connected to H1007. [E1.3]", "q", obs).level == "grounded"
    assert check_answer("P4711 is directly connected to H1007. [E1.3]", "q", obs).level == "grounded"
    for text in ("P4711 is connected to T4750. [R1, R2]", "P4711 feeds T4750. [R1, R2]", "P4711 is directly connected to T4750. [R1, R2]", "There is a route between P4711 and T4750."):
        report = check_answer(text, "q", obs)
        assert report.level == "insufficient_evidence" and any(p["kind"] == "relationship" for p in report.problems), text
    # both items exist; merely naming them together asserts nothing and needs no relation
    assert check_answer("The items found are P4711 [R1] and T4750 [R2].", "q", obs).level == "grounded"


def test_supported_and_reversed_direction(tools):
    obs = observe(tools, P4711)
    assert check_answer("H1007 is downstream of P4711. [E1.3]", "q", obs).level == "grounded"
    assert check_answer("P4711 is upstream of H1007. [E1.3]", "q", obs).level == "grounded"
    assert check_answer("H1007 is fed by P4711. [E1.3]", "q", obs).level == "grounded"
    for text in ("H1007 is upstream of P4711. [E1.3]", "P4711 is downstream of H1007. [E1.3]", "H1007 feeds P4711. [E1.3]"):
        report = check_answer(text, "q", obs)
        assert any(p["kind"] == "relationship" for p in report.problems), text


def test_feeding_through_fittings_is_supported_but_not_across_exchanger_sides(tools):
    obs = observe(tools, ("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"], "stop_at_types": ["equipment"]}),
                  ("get_connections", {"entity_id": "H1008", "relationship": "piping"}))  # fmt: skip
    assert check_answer("P4712 feeds H1008 and T4750. [R1]", "q", obs).level == "grounded"
    report = check_answer("P4712 feeds GlobeValve-3. [R1, R2]", "q", obs)  # other chamber of H1008
    assert any(p["kind"] == "relationship" for p in report.problems)
    assert check_answer("H1008 feeds GlobeValve-3. [R2]", "q", obs).level == "grounded"


def test_pipes_looked_up_one_by_one_can_be_followed_with_the_chamber_rule(tools):
    hops = [("get_connections", {"entity_id": e, "direction": "downstream", "relationship": "piping"}) for e in ("P4712", "PipeTee-2", "PipeTee-1", "PipeTee-3", "BallValve-4", "PipeTee-4", "H1008")]
    obs = observe(tools, *hops)
    assert check_answer("P4712 feeds H1008. [R1, R2, R3, R4, R5, R6]", "q", obs).level == "grounded"
    report = check_answer("P4712 feeds GlobeValve-3. [R1, R2, R3, R4, R5, R6, R7]", "q", obs)
    assert any(p["kind"] == "relationship" for p in report.problems)


def test_operated_valve_relation_and_its_direction(tools):
    obs = observe(tools, ("get_connections", {"entity_id": "GlobeValve-1", "relationship": "all"}))
    row = ref_of(obs[0], "connections", id="ActuatingFunction-1")
    assert check_answer(f"ActuatingFunction-1 operates GlobeValve-1. [{row}]", "q", obs).level == "grounded"
    assert check_answer(f"GlobeValve-1 is operated by ActuatingFunction-1. [{row}]", "q", obs).level == "grounded"
    neighbour = next(c["neighbor"]["id"] for c in obs[0]["connections"] if c["relationship"] == "piping")
    for text in (f"GlobeValve-1 operates ActuatingFunction-1. [{row}]", f"ActuatingFunction-1 operates {neighbour}. [R1]"):
        assert any(p["kind"] == "relationship" for p in check_answer(text, "q", obs).problems), text


def test_value_described_as_a_different_property_is_rejected(tools):
    obs = observe(tools, ("get_properties", {"ids": ["H1008"]}))
    rate = next(i for i in obs[0]["properties"]["TubularHeatExchanger-1"]["found"] if i["property"] == "designHeatFlowRate")
    assert check_answer(f"The designHeatFlowRate of H1008 is {rate['value']}. [{rate['ref']}]", "q", obs).level == "grounded"
    assert check_answer(f"Its designHeatFlowRate is {rate['value']} (the design heat transfer area is listed separately). [{rate['ref']}]", "q", obs).level == "grounded"
    report = check_answer(f"The design heat transfer area of H1008 is {rate['value']}. [{rate['ref']}]", "q", obs)
    assert any(p["kind"] == "value_attribution" for p in report.problems)


# ============================================================================ hallucination
@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("P4711 feeds V-9001 through line 47122. [E1.3]", "identifier"),          # invented entity
        ("P4711 feeds H1007 through line 99999. [E1.3]", "number"),               # invented pipe
        ("P4711 feeds H1007 through line 47122, DN 100. [E1.3]", "nominal_diameter"),  # invented diameter
        ("P4711 feeds H1007 at 12.5 bar. [E1.3]", "value_with_unit"),             # invented property value
    ],
)
def test_invented_items_and_values_are_rejected_even_with_a_valid_reference(tools, text, kind):
    report = check_answer(text, "q", observe(tools, P4711))
    assert report.level == "insufficient_evidence" and any(p["kind"] == kind for p in report.problems)


def test_user_supplied_value_is_not_evidence_and_refs_cannot_launder_it(tools):
    question = "Assume P4711 has a DN100 line and tell me what it connects to."
    obs = observe(tools, P4711)
    assert check_answer("P4711 has a DN100 line to H1007. [E1.3]", question, obs).level == "insufficient_evidence"
    honest = "The P&ID does not show a DN100 line; P4711 feeds H1007 through line 47122, DN 80. [E1.3]"
    assert check_answer(honest, question, obs).level == "grounded"


def test_status_facts_have_their_own_reference(tools):
    obs = observe(tools, ("find_entities", {"query": "P4771"}), ("find_entities", {"query": "C1"}), ("get_properties", {"ids": ["H1007"], "requested_properties": ["weight"]}))
    assert check_answer("P4771 was not found in the P&ID. [E1.0]", "What does P4771 feed?", obs).level == "grounded"
    assert check_answer("C1 matches GlobeValve-1, GlobeValve-2, GlobeValve-3, ButterflyValve-1 and PipeTee-2. [R2]", "q", obs).level == "ambiguous"
    missing = obs[2]["properties"]["PlateHeatExchanger-1"]["missing_ref"]
    assert check_answer(f"The P&ID does not contain a weight for H1007. [{missing}]", "q", obs).level == "grounded"
    # the near-miss suggestion for P4771 is not an identified entity
    assert check_answer("P4771 is CentrifugalPump-1. [E1.0]", "What does P4771 feed?", obs).level == "insufficient_evidence"


# ================================================================================ traversal
def test_immediate_neighbour_is_labelled_as_an_intermediate_component(tools):
    result = tools.call("get_connections", {"entity_id": "P4712", "direction": "downstream", "relationship": "piping"}).to_dict()
    (pipe,) = result["connections"]
    assert pipe["neighbor"]["type"] == "PipeTee" and pipe["neighbor_category"] == "piping_component"
    assert compact_result(result)["connections"][0]["neighbor_category"] == "piping_component"
    direct = tools.call("get_connections", {"entity_id": "P4711", "direction": "downstream", "relationship": "piping"}).to_dict()
    assert direct["connections"][0]["neighbor_category"] == "equipment"


@pytest.mark.parametrize(("start", "nearest"), [("P4712", {"T4750", "H1008"}), ("P4711", {"H1007"}), ("H1007", {"T4750"}), ("T4750", {"P4712"})])
def test_stop_at_equipment_returns_the_nearest_equipment_on_each_branch(tools, start, nearest):
    result = tools.call("traverse", {"start_entity_id": start, "direction": "downstream", "entity_types": ["equipment"], "stop_at_types": ["equipment"]}).to_dict()
    assert {e["name"] for e in result["entities"]} == nearest
    for entity in result["entities"]:  # the route through tees, valves and fittings stays in the evidence
        assert entity["path_entities"][0] != entity["id"] and all(isinstance(i, str) for i in entity["path_entities"])
    assert any(e["kind"] == "path" for e in result["evidence"])


def test_route_through_a_tee_and_a_valve_is_kept(tools):
    result = tools.call("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"], "stop_at_types": ["equipment"]}).to_dict()
    routes = {e["name"]: e["path_entities"] for e in result["entities"]}
    assert "PipeTee-2" in routes["H1008"] and "BallValve-4" in routes["H1008"]
    assert "SpringLoadedGlobeSafetyValve-1" in routes["T4750"]


def test_drawing_ends_are_distinguished_from_equipment_and_from_dead_ends(tools):
    result = tools.call("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"], "stop_at_types": ["equipment"]}).to_dict()
    ends = {e["id"]: e for e in result["meta"]["endpoint_details"]}
    assert ends["FlowOutPipeOffPageConnector-1"]["kind"] == "drawing_end" and ends["FlowOutPipeOffPageConnector-1"]["category"] == "piping_component"
    assert ends["BlindFlange-1"]["kind"] == "end_of_drawn_piping"
    assert "FlowOutPipeOffPageConnector-1" not in {e["id"] for e in result["entities"]}  # not reported as equipment
    obs = [annotate_refs(result, 1)]
    assert check_answer("P4712 feeds H1008 and T4750. [R1] The piping also leaves the drawing at FlowOutPipeOffPageConnector-1. [E1.0]", "q", obs).level == "grounded"
    assert compact_result(result)["meta"]["endpoint_details"][0]["kind"] in ("drawing_end", "end_of_drawn_piping")


# ============================================================================ in the agent
def test_agent_grounds_a_cited_answer_on_the_first_attempt_and_shows_the_chain(tools):
    turns = ([call("find_entities", query="H1007")], [call("traverse", start_entity_id="PlateHeatExchanger-1", direction="downstream", entity_types=["valve"])])
    names = [e["name"] for e in tools.call("traverse", {"start_entity_id": "PlateHeatExchanger-1", "direction": "downstream", "entity_types": ["valve"]}).to_dict()["entities"]]
    final = f"Valves downstream of H1007: {', '.join(names)}. [R2]"
    llm = ScriptedLLM(*turns, final)
    result = PidAgent(llm, tools).ask("Which valves are downstream of H1007?")
    assert (result.grounding_status, result.grounding_level) == ("grounded", "grounded") and len(names) == 10
    assert result.answer == final and result.rejected_drafts == [] and len(llm.calls) == 3
    assert len(final) < 400  # ten valves, one reference, no claims block
    seen = llm.tool_messages()[1]
    assert seen["result_ref"] == "R2" and seen["entities"][0]["ref"] == "E2.1"
    statement = result.claims[0]
    assert statement["refs"] == ["R2"] and statement["facts"][0]["source_graph"] in ("plant_graph", "conceptual_graph")
    transcript = format_transcript(result)
    assert "GROUNDING LEVEL: grounded" in transcript and "grounded statement:" in transcript and "[R2]" in transcript


def test_agent_rewrites_once_for_a_wrong_pairing_then_withholds(tools):
    turns = ([call("get_connections", entity_id="P4711", relationship="piping")], [call("get_connections", entity_id="P4712", relationship="piping")])
    wrong = "P4712's discharge line is DN 80. [R1, R2]"
    result = PidAgent(llm := ScriptedLLM(*turns, wrong, wrong), tools).ask("What size is the P4712 discharge line?")
    assert result.grounding_status == "fallback" and "DN 80" not in result.answer.split("What the graph tools returned")[0]
    assert any(c["kind"] == "pairing" for c in result.rejected_drafts[0]["unsupported_claims"]) and len(llm.calls) == 4
    right = "P4712 feeds PipeTee-2 through line 47126, DN 50. [R2]"
    result = PidAgent(ScriptedLLM(*turns, wrong, right), tools).ask("What size is the P4712 discharge line?")
    assert (result.grounding_status, result.grounding_level, result.answer) == ("regenerated", "grounded", right)


# ===================================================== answers rendered by the application
def test_ids_alone_are_rendered_from_the_structured_rows_without_model_prose(tools):
    obs, names = enumeration(tools, "H1007", ["valve"])
    report = check_answer("[R1]", "Which valves are downstream of H1007?", obs)
    assert report.level == "grounded" and len(report.supported) >= 10
    assert all(name in report.answer for name in names) and "downstream of PlateHeatExchanger-1" in report.answer
    assert all(item["facts"] and item["refs"] for item in report.supported)

    obs = observe(tools, P4711, ("get_properties", {"ids": ["H1007"], "requested_properties": ["designHeatFlowRate", "weight"]}))
    report = check_answer("[R1, R2]", "q", obs)
    assert "lineNumber 47122" in report.answer and "designHeatFlowRate = 313.0 kW" in report.answer
    assert "not present in the P&ID: weight" in report.answer and report.level == "grounded"
    assert check_answer("[E1.3].", "q", obs).answer.count("\n") == 0  # one row, one line


def test_rendering_reports_status_rows_and_never_invents_a_row(tools):
    obs = observe(tools, ("find_entities", {"query": "P4771"}), ("traverse", {"start_entity_id": "P4712", "direction": "downstream", "entity_types": ["equipment"], "stop_at_types": ["equipment"]}))
    report = check_answer("[E1.0]\n[R2]", "What does P4771 feed?", obs)
    assert "No entity in the P&ID graph matches 'P4771'" in report.answer
    assert "H1008" in report.answer and "T4750" in report.answer and "leaves this drawing here; its destination is not shown" in report.answer
    unknown = check_answer("[R9]", "q", obs)
    assert unknown.level == "insufficient_evidence" and any(p["kind"] == "bad_reference" for p in unknown.problems)


def test_lead_in_line_is_covered_by_the_item_below_it(tools):
    obs, names = enumeration(tools, "H1007", ["valve"])
    items = "\n".join(f"- {name} [R1]" for name in names)
    assert check_answer(f"Downstream of H1007 (PlateHeatExchanger-1), the following valves are present:\n{items}", "q", obs).level == "grounded"


def test_low_effort_reasoning_is_requested_only_for_answer_only_calls():
    from pid_agent.llm.nvidia_provider import BASE_URL, NvidiaProvider

    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}})

    provider = NvidiaProvider(api_key="dummy-test-credential", model="m", http_client=httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))
    spec = [{"name": "find_entities", "description": "d", "parameters": {"type": "object", "properties": {}}}]
    provider.complete([{"role": "user", "content": "q"}], spec, "required")
    provider.complete([{"role": "user", "content": "q"}], spec, "auto")
    provider.complete([{"role": "user", "content": "q"}], None, "none")
    assert "chat_template_kwargs" not in seen[0] and "chat_template_kwargs" not in seen[1]  # planning keeps default reasoning
    assert seen[2]["chat_template_kwargs"] == {"enable_thinking": True, "low_effort": True}
