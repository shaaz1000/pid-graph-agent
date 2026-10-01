"""The grounding validator on its own: what counts as a claim and what counts as evidence."""

from __future__ import annotations

import pytest

from pid_agent.agent.grounding import check_grounding, extract_claims


@pytest.fixture(scope="module")
def observations(tools):
    return [
        tools.call("find_path", {"source_entity_id": "CentrifugalPump-1", "target_entity_id": "PlateHeatExchanger-1"}).to_dict(),
        tools.call("get_properties", {"ids": ["CentrifugalPump-1"], "requested_properties": ["designShaftPower", "manufacturer"]}).to_dict(),
    ]


def claims(text):
    return {(c.text, c.kind) for c in extract_claims(text)}


def test_claim_extraction_finds_plant_specific_tokens():
    found = claims("P4711 (CentrifugalPump-1) feeds H1007 through line 47122, DN 80, at 60.0 kW; code 73KH12.")
    assert found == {
        ("P4711", "identifier"), ("CentrifugalPump-1", "identifier"), ("H1007", "identifier"),
        ("47122", "number"), ("DN 80", "nominal_diameter"), ("60.0 kW", "value_with_unit"), ("73KH12", "identifier"),
    }  # fmt: skip


def test_ordinary_prose_yields_no_claims():
    assert claims("The pump feeds the heat exchanger directly. There are 2 pumps and 11 valves; see the 1st one.") == set()


def test_connection_ids_and_type_names_are_claims():
    assert ("PipingNetworkSegment-2/connections/1", "identifier") in claims("via PipingNetworkSegment-2/connections/1.")
    assert ("PlateHeatExchanger", "type_name") in claims("It is a PlateHeatExchanger.")


@pytest.mark.parametrize(
    "answer",
    [
        "P4711 (CentrifugalPump-1) is connected to H1007 (PlateHeatExchanger-1) by line 47122, segment S1, DN 80.",
        "The pipe is DN80 per DN 80 (DIN 2448), fluid MNb, class 75HB13, from nozzle N2 to N1 of Chamber-1.",
        "The design shaft power of P4711 is 60.0 kW.",
        "The design shaft power of P4711 is 60 kW.",  # same number, different formatting
        "The supplied P&ID does not contain manufacturer information for P4711.",
    ],
)
def test_supported_answers_pass(observations, answer):
    report = check_grounding(answer, "question", observations)
    assert report.grounded, report.unsupported
    assert report.claims_checked > 0


@pytest.mark.parametrize(
    ("answer", "bad"),
    [
        ("P4711 is connected to H1007 by line 47122, DN 100.", "DN 100"),
        ("P4711 feeds H1008.", "H1008"),
        ("The shaft power of P4711 is 75.0 kW.", "75.0 kW"),
        ("The line is 47199.", "47199"),
        ("The operating pressure of P4711 is 12.5 bar.", "12.5 bar"),
        ("P4711 is made by ACME, model XR-200.", "XR-200"),
        ("H1007 is a ShellAndTubeExchanger.", "ShellAndTubeExchanger"),
        ("The pipe is 80 mm wide.", "80 mm"),  # DN 80 is in the graph; a width in mm is not
    ],
)
def test_invented_facts_are_flagged(observations, answer, bad):
    report = check_grounding(answer, "question", observations)
    assert [c["claim"] for c in report.unsupported] == [bad]
    assert report.unsupported[0]["reason"] == "not found in any tool result"


def test_tool_inputs_and_messages_are_not_evidence(tools):
    result = tools.call("find_entities", {"query": "P4771"}).to_dict()
    assert "P4771" in result["message"] and result["input"]["query"] == "P4771"
    report = check_grounding("P4771 is a centrifugal pump.", "unrelated question", [result])
    assert [c["claim"] for c in report.unsupported] == ["P4771"]


def test_unknown_id_echoed_by_get_properties_is_not_evidence(tools):
    result = tools.call("get_properties", {"ids": ["Pump-99"], "requested_properties": ["tagName"]}).to_dict()
    assert not check_grounding("Pump-99 exists.", "q", [result]).grounded


def test_suggestions_are_evidence_as_candidates(tools):
    result = tools.call("find_entities", {"query": "P4771"}).to_dict()
    answer = "P4771 was not found in the P&ID. Similar tags are P4711 and P4712."
    assert check_grounding(answer, "What does P4771 feed?", [result]).grounded


def test_question_term_stated_as_fact_is_flagged(observations):
    question = "Assume P4711 has DN100 piping. What does it connect to?"
    report = check_grounding("P4711 has DN100 piping and connects to H1007.", question, observations)
    assert [c["claim"] for c in report.unsupported] == ["DN100"]
    assert "appears only in the question" in report.unsupported[0]["reason"]


def test_question_term_marked_as_unverified_is_allowed(observations):
    question = "Assume P4711 has DN100 piping. What does it connect to?"
    answer = "P4711 connects to H1007 via line 47122, which is DN 80. The graph does not confirm the assumed DN100."
    assert check_grounding(answer, question, observations).grounded


def test_no_evidence_means_any_plant_claim_is_unsupported():
    report = check_grounding("P4711 feeds H1007 through a DN 80 line.", "What does the pump feed?", [])
    assert {c["claim"] for c in report.unsupported} == {"P4711", "H1007", "DN 80"}


def test_abstention_without_claims_is_grounded():
    report = check_grounding("I couldn't determine that from the supplied P&ID graph.", "q", [])
    assert report.grounded and report.claims_checked == 0


def test_typographic_minus_hyphen_and_spaces_do_not_cause_false_alarms(tools):
    observations = [tools.call("get_properties", {"ids": ["PlateHeatExchanger-1"], "requested_properties": ["design pressure"]}).to_dict()]
    answer = "Chamber‑1 of H1007 is rated −1.0 bar to 60.0 bar; Chamber‑2 up to 30.0 bar."
    report = check_grounding(answer, "q", observations + [tools.call("find_entities", {"query": "H1007"}).to_dict()])
    assert report.grounded, report.unsupported
    assert report.claims_checked >= 5


def test_sign_matters(tools):
    observations = [tools.call("get_properties", {"ids": ["PlateHeatExchanger-1"], "requested_properties": ["lowerLimitDesignPressure"]}).to_dict()]
    assert not check_grounding("The lower limit is 1.0 bar.", "q", observations).grounded


@pytest.mark.parametrize("dash", ["-", "–", "−", "‑", "– "])
def test_any_dash_before_a_negative_value_is_accepted(tools, dash):
    observations = [tools.call("get_properties", {"ids": ["PlateHeatExchanger-1"], "requested_properties": ["design pressure"]}).to_dict()]
    assert check_grounding(f"The range is {dash}1.0 bar to 60.0 bar.", "q", observations).grounded


# ------------------------------------------------ context-aware checks
@pytest.fixture(scope="module")
def route(tools):
    return [tools.call("find_path", {"source_entity_id": "Tank-1", "target_entity_id": "ReciprocatingPump-1"}).to_dict()]


def test_identifier_used_in_the_wrong_role_is_flagged(route):
    report = check_grounding("The diameter changes at the reducer (line 47124, segment C3).", "q", route)
    assert [(c["claim"], c["kind"]) for c in report.unsupported] == [("segment C3", "identifier_role")]
    assert "not as a segment" in report.unsupported[0]["reason"]


@pytest.mark.parametrize(
    "answer",
    [
        "The diameter changes at PipeReducer-1 on line 47124, between segment S2 and segment S3.",
        "Component C3 is the reducer; it sits in segment PipingNetworkSegment-5.",
        "The pipe enters the pump at nozzle N1 on line number 47124.",
        "This line has three segments and a component in each segment.",  # prose, no identifiers
    ],
)
def test_identifiers_in_the_right_role_pass(route, tools, answer):
    observations = route + [tools.call("get_entity", {"entity_id": "PipeReducer-1"}).to_dict()]
    report = check_grounding(answer, "q", observations)
    assert report.grounded, report.unsupported


def test_line_number_known_only_from_a_line_component_identifier_passes(tools):
    observations = [tools.call("find_entities", {"query": "globe valve on line 47127"}).to_dict()]
    assert check_grounding("GlobeValve-1 is the globe valve on line 47127.", "q", observations).grounded


def test_other_roles_are_flagged_too(route):
    report = check_grounding("The butterfly valve is on line S1 as component 47124.", "q", route)
    assert {c["claim"] for c in report.unsupported} == {"line S1", "component 47124"}


@pytest.fixture(scope="module")
def pump(tools):
    return [tools.call("get_properties", {"ids": ["CentrifugalPump-1"]}).to_dict()]


def test_correct_value_attached_to_the_wrong_property_is_flagged(pump):
    report = check_grounding("The design pressure head of P4711 is 60.0 kW.", "q", pump)
    assert [(c["claim"], c["kind"]) for c in report.unsupported] == [("60.0 kW", "value_attribution")]
    assert "designShaftPower" in report.unsupported[0]["reason"] and "designPressureHead" in report.unsupported[0]["reason"]


@pytest.mark.parametrize(
    "answer",
    [
        "The design shaft power of P4711 is 60.0 kW.",
        "P4711: pressure head 10.0 m, volume flow rate 200.0 m3/h, shaft power 60.0 kW.",
        "P4711: head 10.0 m, flow 200.0 m3/h, speed 600.0 min-1, power 60.0 kW.",
        "| P4711 | 200.0 m3/h | 60.0 kW |",
        "Its chamber is rated up to 60.0 bar (upper limit design pressure) and down to -0.5 bar.",
    ],
)
def test_correct_attributions_and_terse_lists_pass(pump, answer):
    report = check_grounding(answer, "q", pump)
    assert report.grounded, report.unsupported
