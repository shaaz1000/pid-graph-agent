"""Each of the seven graph tools, exercised against the real C01 graph (no LLM)."""

from __future__ import annotations

import json

import pytest

from conftest import ids
from pid_agent.agent.tools import TOOL_ARGS, tool_specs

VALVES = {
    "GlobeValve-1", "GlobeValve-2", "GlobeValve-3", "ButterflyValve-1", "SwingCheckValve-1",
    "SpringLoadedGlobeSafetyValve-1", "BallValve-1", "BallValve-2", "BallValve-3", "BallValve-4", "BallValve-5",
}  # fmt: skip


def connection_ids(result) -> set[str]:
    return {c["id"] for c in result.connections}


# ------------------------------------------------------------------ envelope
def test_graph_tools_are_exposed_with_schemas():
    specs = tool_specs()
    assert [s["name"] for s in specs] == [
        "find_entities", "list_entities", "get_entity", "get_connections", "traverse", "find_path", "get_properties",
        "isolation_boundary", "trace_instrumentation", "trace_line",
    ]
    assert all(s["description"] and s["parameters"]["type"] == "object" for s in specs)


@pytest.mark.parametrize("name", list(TOOL_ARGS))
def test_every_result_is_structured_and_json_serialisable(tools, name):
    result = tools.call(name, {})  # mostly invalid arguments: must still be a clean result
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["tool"] == name
    assert {"status", "entities", "connections", "evidence", "warnings", "meta"} <= set(payload)


def test_unknown_tool_and_bad_arguments_do_not_raise(tools):
    assert tools.call("drop_database", {}).status == "error"
    bad = tools.call("traverse", {"start": "P4711"})
    assert bad.status == "error" and "start_entity_id" in bad.message
    assert tools.call("get_entity", {"entity_id": "P4711", "shell": "rm -rf /"}).status == "error"
    assert tools.call("traverse", {"start_entity_id": "P4711", "direction": "downstream", "max_depth": "deep"}).status == "error"


def test_evidence_only_references_known_objects(index, tools):
    known = set(index.entities) | set(index.connections) | set(index.objects)
    calls = [
        ("find_entities", {"query": "73KH12"}),
        ("get_entity", {"entity_id": "PlateHeatExchanger-1", "include_children": True}),
        ("get_connections", {"entity_id": "PlateHeatExchanger-1"}),
        ("traverse", {"start_entity_id": "CentrifugalPump-1", "direction": "downstream"}),
        ("find_path", {"source_entity_id": "CentrifugalPump-1", "target_entity_id": "Tank-1"}),
        ("get_properties", {"ids": ["Tank-1"]}),
    ]
    for name, arguments in calls:
        result = tools.call(name, arguments)
        assert result.evidence, name
        for item in result.evidence:
            assert item.source_object_ids and set(item.source_object_ids) <= known, (name, item.id)


# ------------------------------------------------------------ find_entities
def test_find_entities_unique(service):
    result = service.find_entities("P4711")
    assert result.status == "success" and ids(result) == ["CentrifugalPump-1"]
    assert result.entities[0]["match_tier"] == "exact_tag" and result.entities[0]["confidence"] == 1.0
    assert result.resolution == {"status": "unique", "ambiguous": False, "match_count": 1, "suggestions": []}


def test_find_entities_ambiguous(service):
    result = service.find_entities("73KH12")
    assert result.status == "ambiguous" and len(result.entities) == 5
    assert result.resolution["ambiguous"] is True
    assert all(e["match_reason"] == "pipingComponentName = '73KH12'" for e in result.entities)


def test_find_entities_unknown(service):
    result = service.find_entities("X9999")
    assert result.status == "not_found" and result.entities == [] and result.evidence == []


def test_find_entities_near_miss_is_not_bound(service):
    result = service.find_entities("H1070")
    assert result.status == "not_found" and result.entities == []
    assert result.resolution["suggestions"]


def test_find_entities_with_type_filter(service):
    assert ids(service.find_entities("C1", entity_type="butterfly valve")) == ["ButterflyValve-1"]


# ------------------------------------------------------------ list_entities
def test_list_entities_by_supertype(service):
    assert ids(service.list_entities("pump")) == ["CentrifugalPump-1", "ReciprocatingPump-1"]
    assert set(ids(service.list_entities("valves"))) == VALVES
    assert ids(service.list_entities("HeatExchanger")) == ["PlateHeatExchanger-1", "TubularHeatExchanger-1"]


def test_list_entities_by_category(service):
    assert len(service.list_entities("equipment").entities) == 5
    assert len(service.list_entities("instrumentation").entities) == 10
    assert len(service.list_entities("line").entities) == 11


def test_list_entities_unknown_type_is_empty_with_catalogue(service):
    result = service.list_entities("compressor")
    assert result.status == "empty" and result.entities == []
    assert "CentrifugalPump" in result.properties["types"]


def test_list_entities_without_type_returns_catalogue(service):
    result = service.list_entities()
    assert result.properties["types"]["BallValve"] == 5
    assert result.properties["categories"] == {"piping_component": 21, "instrumentation": 10, "equipment": 5, "piping_line": 11}


# --------------------------------------------------------------- get_entity
def test_get_entity(service):
    result = service.get_entity("CentrifugalPump-1")
    entity = result.entities[0]
    assert entity["tag"] == "P4711" and entity["type"] == "CentrifugalPump"
    assert entity["properties"]["designVolumeFlowRate"] == "200.0 m3/h"
    assert "children" not in entity
    assert {"id": "Nozzle-1", "type": "Nozzle"} in entity["children_available"]


def test_get_entity_with_children(service):
    entity = service.get_entity("PlateHeatExchanger-1", include_children=True).entities[0]
    chambers = [c for c in entity["children"] if c["type"] == "Chamber"]
    assert len(chambers) == 2


def test_get_entity_accepts_a_unique_tag_and_says_so(service):
    result = service.get_entity("h1007")
    assert ids(result) == ["PlateHeatExchanger-1"]
    assert any("resolved it to PlateHeatExchanger-1" in w for w in result.warnings)


def test_get_entity_unknown_and_ambiguous(service):
    assert service.get_entity("Pump-99").status == "not_found"
    ambiguous = service.get_entity("73KH12")
    assert ambiguous.status == "ambiguous" and len(ambiguous.entities) == 5


def test_get_entity_for_a_line_lists_segments(service):
    entity = service.get_entity("PipingNetworkSystem-4", include_children=True).entities[0]
    assert [c["id"] for c in entity["children"]] == [f"PipingNetworkSegment-{i}" for i in (4, 5, 6)]
    assert entity["children"][0]["properties"]["items"] == ["ButterflyValve-1", "SwingCheckValve-1"]


# ---------------------------------------------------------- get_connections
def test_get_connections_both(service):
    result = service.get_connections("CentrifugalPump-1")
    by_neighbour = {c["neighbor"]["id"]: c for c in result.connections}
    assert set(by_neighbour) == {"FlowInPipeOffPageConnector-1", "PlateHeatExchanger-1"}
    assert by_neighbour["PlateHeatExchanger-1"]["neighbor_is"] == "downstream"
    assert by_neighbour["FlowInPipeOffPageConnector-1"]["neighbor_is"] == "upstream"
    assert by_neighbour["PlateHeatExchanger-1"]["properties"]["lineNumber"] == "47122"


def test_get_connections_downstream_and_upstream(service):
    down = service.get_connections("Tank-1", "downstream", "piping")
    assert [c["neighbor"]["id"] for c in down.connections] == ["ButterflyValve-1"]
    up = service.get_connections("Tank-1", "upstream", "piping")
    assert {c["neighbor"]["id"] for c in up.connections} == {"GlobeValve-1", "GlobeValve-2", "SpringLoadedGlobeSafetyValve-1"}


def test_get_connections_empty_result(service):
    result = service.get_connections("BlindFlange-1", "downstream", "piping")
    assert result.status == "empty" and result.connections == []


def test_get_connections_invalid_direction_and_relationship(service):
    assert service.get_connections("Tank-1", "outgoing").status == "error"
    assert service.get_connections("Tank-1", "both", "electrical").status == "error"


def test_get_connections_unknown_entity(service):
    assert service.get_connections("Valve-404").status == "not_found"


def test_get_connections_instrumentation(service):
    result = service.get_connections("GlobeValve-1", relationship="instrumentation")
    assert [(c["connection_type"], c["neighbor"]["id"]) for c in result.connections] == [("operated_valve_reference", "ActuatingFunction-1")]


def test_get_connections_includes_open_ends_without_inventing_a_neighbour(service):
    result = service.get_connections("PlateHeatExchanger-1", relationship="piping")
    open_ends = [c for c in result.connections if c.get("open_end")]
    assert {c["id"] for c in open_ends} == {"PipingNetworkSegment-20/connections/1", "PipingNetworkSegment-21/connections/1"}
    for connection in open_ends:
        assert connection["neighbor"] is None
        assert connection["connection_type"] == "open_end"
        assert connection["provenance"]["derived_from"] == "plant_graph"
        assert connection["provenance"]["present_in_conceptual_graph"] is False
    assert {c["neighbor_is"] for c in open_ends} == {"upstream", "downstream"}
    assert any("open-ended" in w for w in result.warnings)
    assert {e.kind for e in result.evidence} == {"connection", "open_end"}


def test_get_connections_rejects_a_line(service):
    result = service.get_connections("PipingNetworkSystem-2")
    assert result.status == "error" and "not a node in the connection topology" in result.message


# ----------------------------------------------------------------- traverse
def test_traverse_downstream_with_type_filter(service):
    result = service.traverse("CentrifugalPump-1", "downstream", entity_types=["heat exchanger"])
    assert [(e["id"], e["distance"]) for e in result.entities] == [("PlateHeatExchanger-1", 1), ("TubularHeatExchanger-1", 14)]
    assert result.entities[0]["path_entities"] == ["CentrifugalPump-1", "PlateHeatExchanger-1"]
    assert result.entities[0]["path_connections"] == ["PipingNetworkSegment-2/connections/1"]


def test_traverse_upstream(service):
    result = service.traverse("CentrifugalPump-1", "upstream")
    assert ids(result) == ["FlowInPipeOffPageConnector-1"] and not result.meta["cycle_detected"]


def test_traverse_depth_bound(service):
    shallow = service.traverse("Tank-1", "upstream", max_depth=1)
    assert set(ids(shallow)) == {"GlobeValve-1", "GlobeValve-2", "SpringLoadedGlobeSafetyValve-1"}
    assert shallow.meta["truncated_by_max_depth"] and any("max_depth=1" in w for w in shallow.warnings)
    assert all(e["distance"] <= 2 for e in service.traverse("Tank-1", "upstream", max_depth=2).entities)


def test_traverse_depth_is_clamped(service):
    result = service.traverse("Tank-1", "downstream", max_depth=10_000)
    assert result.meta["max_depth"] == 25 and any("clamped" in w for w in result.warnings)
    assert service.traverse("Tank-1", "downstream", max_depth=0).meta["max_depth"] == 1


def test_traverse_recycle_loop_terminates_and_reports_each_entity_once(service):
    # T4750 -> butterfly -> check valve -> reducer -> ball valve -> P4712 -> ... -> SV -> T4750
    result = service.traverse("ReciprocatingPump-1", "downstream")
    reached = ids(result)
    assert len(reached) == len(set(reached)) == 20
    assert "ReciprocatingPump-1" not in reached
    assert result.meta["cycle_detected"] and result.meta["start_is_in_cycle"]
    assert not result.meta["truncated_by_max_depth"]
    tank = next(e for e in result.entities if e["id"] == "Tank-1")
    assert tank["distance"] == 4
    assert tank["path_entities"] == ["ReciprocatingPump-1", "PipeTee-2", "PipeTee-1", "SpringLoadedGlobeSafetyValve-1", "Tank-1"]


def test_traverse_upstream_around_the_loop_mirrors_downstream(service):
    upstream_of_tank = set(ids(service.traverse("Tank-1", "upstream")))
    assert {"ReciprocatingPump-1", "CentrifugalPump-1", "FlowInPipeOffPageConnector-1"} <= upstream_of_tank
    assert "FlowOutPipeOffPageConnector-1" not in upstream_of_tank  # only leaves the loop
    assert "Tank-1" in ids(service.traverse("ReciprocatingPump-1", "downstream"))


def test_traverse_stop_at_types_is_plain_mechanics(service):
    result = service.traverse("ReciprocatingPump-1", "downstream", stop_at_types=["equipment"])
    assert set(result.meta["stopped_at"]) == {"Tank-1", "TubularHeatExchanger-1"}
    reached = set(ids(result))
    assert {"Tank-1", "TubularHeatExchanger-1"} <= reached           # stop nodes are reported
    assert not {"ButterflyValve-1", "GlobeValve-1"} & reached         # nothing beyond them
    assert not result.meta["cycle_detected"]


def test_traverse_does_not_cross_exchanger_sides(service):
    # GlobeValve-3 hangs off H1008's other chamber (Chamber-4); the pump feeds Chamber-3.
    result = service.traverse("ReciprocatingPump-1", "downstream")
    assert "TubularHeatExchanger-1" in ids(result) and "GlobeValve-3" not in ids(result)
    assert any("separate chambers" in w for w in result.warnings)
    assert "GlobeValve-3" in ids(service.traverse("TubularHeatExchanger-1", "downstream", max_depth=1))


def test_traverse_reports_open_ends_it_runs_into(service):
    result = service.traverse("TubularHeatExchanger-1", "downstream", max_depth=2)
    open_ends = [c for c in result.connections if c.get("open_end")]
    assert [c["id"] for c in open_ends] == ["PipingNetworkSegment-23/connections/2"]
    assert open_ends[0]["target"] is None


def test_traverse_both(service):
    result = service.traverse("BallValve-4", "both", entity_types=["equipment"])
    assert set(ids(result)) == {"Tank-1", "CentrifugalPump-1", "ReciprocatingPump-1", "PlateHeatExchanger-1", "TubularHeatExchanger-1"}


def test_traverse_empty_and_invalid(service):
    assert service.traverse("FlowOutPipeOffPageConnector-1", "downstream").status == "empty"
    assert service.traverse("Tank-1", "sideways").status == "error"
    assert service.traverse("Nope-1", "downstream").status == "not_found"


def test_traverse_unknown_type_filter_warns_and_matches_nothing(service):
    result = service.traverse("CentrifugalPump-1", "downstream", entity_types=["compressor"])
    assert result.status == "empty" and any("'compressor' is not a type" in w for w in result.warnings)


# ---------------------------------------------------------------- find_path
def test_find_path_direct(service):
    result = service.find_path("CentrifugalPump-1", "PlateHeatExchanger-1")
    path = result.paths[0]
    assert path["length"] == 1 and [e["id"] for e in path["entities"]] == ["CentrifugalPump-1", "PlateHeatExchanger-1"]
    pipe = path["steps"][0]["connection"]
    assert pipe["id"] == "PipingNetworkSegment-2/connections/1"
    assert pipe["properties"]["lineNumber"] == "47122"
    assert pipe["properties"]["nominalDiameterRepresentation"] == "DN 80"
    assert pipe["source_nozzle"]["id"] == "Nozzle-2" and pipe["target_nozzle"]["id"] == "Nozzle-3"
    assert [e.kind for e in result.evidence] == ["path", "connection"]


def test_find_path_multi_hop_shows_diameter_change(service):
    result = service.find_path("Tank-1", "ReciprocatingPump-1")
    path = result.paths[0]
    assert [e["id"] for e in path["entities"]] == ["Tank-1", "ButterflyValve-1", "SwingCheckValve-1", "PipeReducer-1", "BallValve-1", "ReciprocatingPump-1"]
    diameters = [s["connection"]["properties"]["nominalDiameterRepresentation"] for s in path["steps"]]
    assert diameters == ["DN 80", "DN 80", "DN 80", "DN 50", "DN 50"]


def test_find_path_respects_flow_direction(service):
    against = service.find_path("PlateHeatExchanger-1", "CentrifugalPump-1")
    assert against.status == "empty" and any("upstream direction" in w for w in against.warnings)
    upstream = service.find_path("PlateHeatExchanger-1", "CentrifugalPump-1", "upstream")
    assert upstream.paths[0]["steps"][0]["travelled"] == "against_flow"
    assert service.find_path("PlateHeatExchanger-1", "CentrifugalPump-1", "any").status == "success"


def test_find_path_no_path_at_all(service):
    result = service.find_path("FlowOutPipeOffPageConnector-1", "CentrifugalPump-1")
    assert result.status == "empty" and result.paths == []


def test_find_path_does_not_cross_exchanger_sides(service):
    result = service.find_path("PipeTee-4", "GlobeValve-3")
    assert result.status == "empty" and any("separate chambers" in w for w in result.warnings)


def test_find_path_to_instrumentation_explains_itself(service):
    result = service.find_path("CentrifugalPump-1", "ProcessSignalGeneratingFunction-1")
    assert result.status == "empty" and any("no piping connections" in w for w in result.warnings)


def test_find_path_errors(service):
    assert service.find_path("CentrifugalPump-1", "CentrifugalPump-1").status == "error"
    assert service.find_path("CentrifugalPump-1", "Nope-1").status == "not_found"
    assert service.find_path("CentrifugalPump-1", "Tank-1", "diagonal").status == "error"
    assert service.find_path("73KH12", "Tank-1").status == "ambiguous"


# ----------------------------------------------------------- get_properties
def test_get_properties_found_and_missing(service):
    result = service.get_properties("CentrifugalPump-1", ["designShaftPower", "manufacturer"])
    report = result.properties["CentrifugalPump-1"]
    assert report["found"] == [{"property": "designShaftPower", "value": "60.0 kW", "source_object_id": "CentrifugalPump-1", "scope": "own"}]
    assert report["missing"] == ["manufacturer"]
    assert "designShaftPower" in report["available"]


def test_get_properties_all_missing_is_empty_not_invented(service):
    result = service.get_properties(["PlateHeatExchanger-1"], ["lastMaintenanceDate", "colour"])
    assert result.status == "empty" and result.evidence == []
    assert result.properties["PlateHeatExchanger-1"]["missing"] == ["lastMaintenanceDate", "colour"]


def test_get_properties_unknown_id(service):
    result = service.get_properties(["Nope-1"], ["tagName"])
    assert result.status == "not_found" and result.properties == {"Nope-1": {"error": "not_found"}}


def test_get_properties_multiple_ids(service):
    result = service.get_properties(["CentrifugalPump-1", "ReciprocatingPump-1"], ["designVolumeFlowRate"])
    values = {k: v["found"][0]["value"] for k, v in result.properties.items()}
    assert values == {"CentrifugalPump-1": "200.0 m3/h", "ReciprocatingPump-1": "420.0 m3/h"}


# ------------------------------------- path facts added for multi-hop reasoning
def test_traverse_rows_say_which_equipment_lies_on_the_way(service):
    rows = {e["id"]: e for e in service.traverse("CentrifugalPump-1", "downstream", entity_types=["equipment"]).entities}
    assert rows["PlateHeatExchanger-1"]["through_equipment"] == []
    assert rows["Tank-1"]["through_equipment"] == ["PlateHeatExchanger-1"]
    assert rows["ReciprocatingPump-1"]["through_equipment"] == ["PlateHeatExchanger-1", "Tank-1"]


def test_traverse_endpoints_are_listed_regardless_of_filters(service):
    result = service.traverse("Tank-1", "downstream", entity_types=["pump"])
    assert [e["id"] for e in result.entities] == ["ReciprocatingPump-1"]
    assert set(result.meta["endpoints"]) == {"FlowOutPipeOffPageConnector-1", "BlindFlange-1", "BlindFlange-2", "BallValve-2"}
    upstream = service.traverse("Tank-1", "upstream")
    assert upstream.meta["endpoints"] == ["FlowInPipeOffPageConnector-1"]
    assert service.traverse("Tank-1", "both").meta["endpoints"] == []  # no travel direction, no endpoints


def test_entity_results_report_link_counts(service):
    assert service.find_entities("T4750").entities[0]["links"] == {"piping_upstream": 3, "piping_downstream": 1, "instrumentation": 1}
    assert service.get_entity("PlateHeatExchanger-1").entities[0]["links"] == {"piping_upstream": 1, "piping_downstream": 1, "open_ended_pipes": 2}
    assert service.get_entity("ProcessInstrumentationFunction-2").entities[0]["links"] == {"instrumentation": 2}
