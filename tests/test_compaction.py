"""The compact view sent to the model must keep everything needed to reason correctly.

Each test runs a real tool against C01 and inspects what the model would see.
"""

from __future__ import annotations

import json

import pytest

from pid_agent.agent.compact import compact_result


@pytest.fixture(scope="module")
def view(tools):
    def _view(name, **arguments):
        return compact_result(tools.call(name, arguments).to_dict())

    return _view


def size(payload) -> int:
    return len(json.dumps(payload, ensure_ascii=False))


# ------------------------------------------- downstream destination reasoning
@pytest.mark.parametrize(
    ("start", "direct", "indirect"),
    [
        ("ReciprocatingPump-1", {"Tank-1", "TubularHeatExchanger-1"}, set()),
        ("CentrifugalPump-1", {"PlateHeatExchanger-1"}, {"Tank-1", "ReciprocatingPump-1", "TubularHeatExchanger-1"}),
        ("Tank-1", {"ReciprocatingPump-1"}, {"TubularHeatExchanger-1"}),
    ],
)
def test_traversal_tells_direct_from_indirect_equipment(view, start, direct, indirect):
    seen = view("traverse", start_entity_id=start, direction="downstream", entity_types=["equipment"])
    rows = {e["id"]: e for e in seen["entities"]}
    assert {i for i, e in rows.items() if not e["through_equipment"]} == direct
    assert {i for i, e in rows.items() if e["through_equipment"]} == indirect
    for row in rows.values():
        assert {"id", "name", "type", "category", "distance", "via", "through_equipment"} <= set(row)


def test_traversal_names_the_equipment_a_path_passes_through(view):
    seen = view("traverse", start_entity_id="CentrifugalPump-1", direction="downstream", entity_types=["tank"])
    assert seen["entities"][0]["through_equipment"] == ["PlateHeatExchanger-1"]


def test_endpoints_survive_a_type_filter(view):
    """Off-page connectors and dead ends are destinations too, even when only equipment is asked for."""
    seen = view("traverse", start_entity_id="ReciprocatingPump-1", direction="downstream", entity_types=["equipment"])
    assert "FlowOutPipeOffPageConnector-1" not in [e["id"] for e in seen["entities"]]
    assert set(seen["meta"]["endpoints"]) == {"FlowOutPipeOffPageConnector-1", "BlindFlange-1", "BlindFlange-2", "BallValve-2"}


def test_unfiltered_traversal_marks_terminal_entities(view):
    seen = view("traverse", start_entity_id="ReciprocatingPump-1", direction="downstream")
    terminal = {e["id"] for e in seen["entities"] if e.get("terminal")}
    assert terminal == {"FlowOutPipeOffPageConnector-1", "BlindFlange-1", "BlindFlange-2", "BallValve-2"}
    assert seen["meta"]["cycle_detected"] and seen["meta"]["start_is_in_cycle"]
    assert any("recycle loop" in w for w in seen["warnings"])
    assert any("separate chambers" in w for w in seen["warnings"])
    assert size(seen) < 8_000


def test_adjacency_view_says_it_is_one_hop_and_names_the_pipe(view):
    seen = view("get_connections", entity_id="ReciprocatingPump-1", direction="downstream", relationship="piping")
    assert "entities" not in seen  # the queried entity is not repeated
    (pipe,) = seen["connections"]
    assert pipe["to"] == "PipeTee-2 (PipeTee 47126/C1)" and pipe["neighbor_is"] == "downstream"
    assert (pipe["lineNumber"], pipe["nominalDiameterRepresentation"], pipe["relationship"]) == ("47126", "DN 50", "piping")


# ------------------------------------------------------------- path reasoning
def test_path_view_keeps_order_direction_and_pipe_properties(view):
    seen = view("find_path", source_entity_id="Tank-1", target_entity_id="ReciprocatingPump-1")
    path = seen["paths"][0]
    assert path["length"] == 5 and path["direction"] == "downstream"
    assert path["entities"][0] == "Tank-1 (T4750)" and path["entities"][-1] == "ReciprocatingPump-1 (P4712)"
    for step in path["steps"]:
        assert {"from", "to", "travelled", "lineNumber", "segmentNumber", "nominalDiameterRepresentation"} <= set(step)
    assert [s["nominalDiameterRepresentation"] for s in path["steps"]] == ["DN 80", "DN 80", "DN 80", "DN 50", "DN 50"]


def test_path_view_keeps_the_reason_when_no_path_exists(view):
    seen = view("find_path", source_entity_id="PipeTee-4", target_entity_id="GlobeValve-3")
    assert seen["status"] == "empty" and "No downstream piping path" in seen["message"]
    assert any("separate chambers" in w for w in seen["warnings"])


# --------------------------------------------------- instrumentation traversal
def test_entity_view_announces_instrumentation_links(view):
    seen = view("find_entities", query="globe valve on line 47127")
    (valve,) = seen["entities"]
    assert valve["id"] == "GlobeValve-1"
    assert valve["links"] == {"piping_upstream": 1, "piping_downstream": 1, "instrumentation": 1}
    assert "ActuatingFunction-1" in valve["identifier_notes"]["operatedValveReference"]
    assert "resolution" not in seen  # nothing to say about a unique match


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        ("GlobeValve-1", {("operated_valve_reference", "ActuatingFunction-1 (PV4712.02) [ActuatingFunction]")}),
        ("ActuatingFunction-3", {
            ("operated_valve_reference", "GlobeValve-3 (GlobeValve 47141/C1) [GlobeValve]"),
            ("signal_line", "ProcessInstrumentationFunction-4 (ProcessInstrumentationFunction TICSA4750.03) [ProcessInstrumentationFunction]"),
        }),
        ("Tank-1", {("sensing_location", "ProcessSignalGeneratingFunction-3 (TT4750.03) [ProcessSignalGeneratingFunction]")}),
    ],
)
def test_instrumentation_links_are_explained_in_words(view, entity, expected):
    seen = view("get_connections", entity_id=entity, relationship="instrumentation")
    assert {(c["type"], c["other_entity"]) for c in seen["connections"]} == expected
    for link in seen["connections"]:
        assert link["relationship"] == "instrumentation" and link["meaning"]
        assert "neighbor_is" not in link  # upstream/downstream never applies to a signal
        assert link["from"] and link["to"]


def test_property_view_shows_where_a_value_was_found(view):
    seen = view("get_properties", ids=["ActuatingFunction-1"], requested_properties=["failAction"])
    assert seen["properties"]["ActuatingFunction-1"]["found"] == [
        {"property": "failAction", "value": "fail close", "on": "ControlledActuator-1", "scope": "child:ControlledActuator"}
    ]


# ---------------------------------------------------- missing-property handling
def test_missing_properties_stay_distinct_from_found_ones(view):
    seen = view("get_properties", ids=["CentrifugalPump-1"], requested_properties=["designShaftPower", "manufacturer"])
    report = seen["properties"]["CentrifugalPump-1"]
    assert report["found"] == [{"property": "designShaftPower", "value": "60.0 kW"}]
    assert report["missing"] == ["manufacturer"]
    assert "designVolumeFlowRate" in report["available"]  # so the model can see what does exist


def test_available_list_is_omitted_when_nothing_is_missing(view):
    seen = view("get_properties", ids=["CentrifugalPump-1"], requested_properties=["designShaftPower"])
    assert "available" not in seen["properties"]["CentrifugalPump-1"]


def test_partial_property_match_is_flagged(view):
    seen = view("get_properties", ids=["CentrifugalPump-1"], requested_properties=["designFlowRate"])
    item = seen["properties"]["CentrifugalPump-1"]["found"][0]
    assert item["property"] == "designVolumeFlowRate" and "partial match" in item["match"]


# ----------------------------------------------------- open-end interpretation
def test_open_end_is_distinguishable_from_no_connection(view):
    with_open_end = view("get_connections", entity_id="GlobeValve-3", direction="downstream", relationship="piping")
    (pipe,) = with_open_end["connections"]
    assert pipe["open_end"] == "target" and pipe["to"] is None and pipe["type"] == "open_end"
    assert pipe["lineNumber"] == "47141" and "not represented" in pipe["note"]
    assert with_open_end["status"] == "success"

    dead_end = view("get_connections", entity_id="BlindFlange-1", direction="downstream", relationship="piping")
    assert dead_end["status"] == "empty" and "connections" not in dead_end


def test_traversal_reports_open_ends_it_reaches(view):
    seen = view("traverse", start_entity_id="TubularHeatExchanger-1", direction="downstream", max_depth=1)
    open_ends = [c for c in seen["connections"] if c.get("open_end")]
    assert len(open_ends) == 1 and open_ends[0]["to"] is None and "note" in open_ends[0]


# --------------------------------------------------------- ambiguity handling
def test_ambiguity_is_explicit_and_lists_every_candidate(view):
    seen = view("find_entities", query="73KH12")
    assert seen["status"] == "ambiguous" and seen["resolution"]["ambiguous"] is True
    assert [e["id"] for e in seen["entities"]] == [f"BallValve-{i}" for i in range(1, 6)]
    lines = {e["identifiers"]["lineComponent"] for e in seen["entities"]}
    assert len(lines) == 5  # what distinguishes the candidates is visible
    assert "does not identify a single one" in seen["message"]


def test_not_found_keeps_suggestions_separate_from_matches(view):
    seen = view("find_entities", query="P4771")
    assert seen["status"] == "not_found" and "entities" not in seen
    assert {s["id"] for s in seen["resolution"]["suggestions"]} == {"CentrifugalPump-1", "ReciprocatingPump-1"}


# -------------------------------------------------------------------- hygiene
def test_no_internal_bookkeeping_reaches_the_model(tools):
    calls = [
        ("find_entities", {"query": "T4750"}),
        ("get_entity", {"entity_id": "Tank-1", "include_children": True}),
        ("get_connections", {"entity_id": "Tank-1"}),
        ("traverse", {"start_entity_id": "Tank-1", "direction": "downstream"}),
        ("find_path", {"source_entity_id": "Tank-1", "target_entity_id": "TubularHeatExchanger-1"}),
    ]
    for name, arguments in calls:
        text = json.dumps(compact_result(tools.call(name, arguments).to_dict()))
        for noise in ("source_object_ids", "provenance", "identifier_origins", "confidence", "duration_ms", "evidence"):
            assert noise not in text, (name, noise)
