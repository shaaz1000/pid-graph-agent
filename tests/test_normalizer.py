"""The normalized index: stable ids, authority rules and provenance."""

from __future__ import annotations

import re

from pid_agent.graph.normalizer import normalize
from pid_agent.ingestion.dexpi_loader import load_plant

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
PIPING_KEYS = ("lineNumber", "segmentNumber", "nominalDiameterRepresentation", "fluidCode", "pipingClassCode")


def test_counts(index):
    assert len(index.entities) == 47  # 36 topology entities + 11 piping lines
    assert sum(e.in_topology for e in index.entities.values()) == 36
    piping = [c for c in index.connections.values() if c.relationship == "piping"]
    assert len(piping) == 31
    assert sum(c.relationship == "instrumentation" for c in index.connections.values()) == 12
    assert index.warnings == []


def test_public_ids_are_deterministic_across_loads(loaded, index):
    again = normalize(load_plant(loaded.source_file))
    assert set(again.entities) == set(index.entities)
    assert set(again.connections) == set(index.connections)
    assert set(again.objects) == set(index.objects)
    for connection_id, connection in index.connections.items():
        other = again.connections[connection_id]
        assert (other.source, other.target, other.properties) == (connection.source, connection.target, connection.properties)


def test_no_graph_uuid_leaks_into_the_index(index):
    dumped = " ".join(e.model_dump_json() for e in index.entities.values())
    dumped += " ".join(c.model_dump_json() for c in index.connections.values())
    dumped += " ".join(index.objects)
    assert not UUID.search(dumped)


def test_pipes_without_proteus_id_get_ids_from_their_segment(index):
    connection = index.connections["PipingNetworkSegment-3/connections/2"]
    assert (connection.source, connection.target) == ("GlobeValve-2", "Tank-1")
    assert connection.provenance.source_object_ids == [
        "PipingNetworkSegment-3/connections/2", "PipingNetworkSegment-3", "PipingNetworkSystem-3",
    ]


def test_conceptual_edge_attributes_match_plant_segments(loaded, index):
    """Edge attributes are used as connection properties; this proves they are safe to use."""
    plant = loaded.plant_graph
    nodes = {d["proteusId"]: (n, d) for n, d in plant.nodes(data=True) if d.get("proteusId")}
    checked = 0
    for connection in index.connections.values():
        if connection.relationship != "piping" or connection.open_end:
            continue
        segment_node, segment = nodes[connection.properties["segment_id"]]
        system = next(plant.nodes[u] for u, _, e in plant.in_edges(segment_node, data=True) if e["attr_name"] == "segments")
        truth = {**system, **segment}
        for key in PIPING_KEYS:
            assert connection.properties[key] == truth[key], (connection.id, key)
        checked += 1
    assert checked == 27


def test_entity_line_context_comes_from_the_owning_segment(index):
    tee = index.entities["PipeTee-1"]
    assert tee.piping_context["lineNumber"] == "47126"
    assert tee.piping_context["segment_id"] == "PipingNetworkSegment-11"
    assert tee.piping_context["nominalDiameterRepresentation"] == "DN 50"
    assert "lineNumber" not in tee.properties  # own properties only


def test_entity_properties_are_own_plant_attributes(index):
    pump = index.entities["CentrifugalPump-1"]
    assert pump.properties["designShaftPower"] == "60.0 kW"
    assert not any(k in pump.properties for k in ("label", "labels", "collapsed_from", "proteusId"))
    assert pump.type_hierarchy == ["CentrifugalPump", "Pump", "Equipment"]
    assert pump.category == "equipment"


def test_children_keep_what_abstraction_removed(index):
    exchanger = index.entities["PlateHeatExchanger-1"]
    children = {c.id: c for c in exchanger.children}
    assert {"Nozzle-3", "Nozzle-4", "Nozzle-13", "Nozzle-14", "Chamber-1", "Chamber-2"} <= set(children)
    assert children["Chamber-2"].properties["upperLimitDesignPressure"] == "30.0 bar"
    assert children["Nozzle-13"].properties["chamber"] == "Chamber-2"


def test_open_ends_are_recovered_and_marked(index):
    open_ends = {c.id: c for c in index.connections.values() if c.open_end}
    assert set(open_ends) == {
        "PipingNetworkSegment-20/connections/1",
        "PipingNetworkSegment-21/connections/1",
        "PipingNetworkSegment-22/connections/1",
        "PipingNetworkSegment-23/connections/2",
    }
    for connection in open_ends.values():
        assert connection.connection_type == "open_end"
        assert connection.provenance.derived_from == "plant_graph"
        assert connection.provenance.present_in_conceptual_graph is False
        assert (connection.source is None) != (connection.target is None)  # never a made-up end
        assert not connection.is_traversable
        assert "not represented" in connection.provenance.note
    inlet = open_ends["PipingNetworkSegment-20/connections/1"]
    assert (inlet.source, inlet.target, inlet.open_end) == (None, "PlateHeatExchanger-1", "source")
    assert inlet.target_nozzle.id == "Nozzle-13" and inlet.target_nozzle.chamber_id == "Chamber-2"
    assert inlet.properties["lineNumber"] == "47130" and inlet.properties["fluidCode"] == "WKa"


def test_native_connections_are_marked_as_conceptual(index):
    native = [c for c in index.connections.values() if not c.open_end]
    assert all(c.provenance.derived_from == "conceptual_graph" for c in native)
    assert all(c.provenance.present_in_conceptual_graph for c in native)
    assert all(c.source and c.target for c in native)


def test_instrumentation_connections_keep_their_type(index):
    link = index.connections["OperatedValveReference-1"]
    assert (link.source, link.target) == ("ActuatingFunction-1", "GlobeValve-1")
    assert (link.relationship, link.connection_type) == ("instrumentation", "operated_valve_reference")
    sensing = index.connections["ProcessSignalGeneratingFunction-3/sensingLocation"]
    assert sensing.target == "Tank-1" and sensing.target_nozzle.id == "Nozzle-17"


def test_lines_are_entities_outside_the_topology(index):
    line = index.entities["PipingNetworkSystem-6"]
    assert line.category == "piping_line" and not line.in_topology
    assert line.identifiers == {"lineNumber": "47126"}
    assert len(line.children) == 10
