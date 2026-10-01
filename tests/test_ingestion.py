"""C01 loads through pyDEXPI and the raw graphs look the way the normalizer assumes."""

from __future__ import annotations

from collections import Counter

import networkx as nx
import pytest

from pid_agent.errors import DataFileNotFoundError, DexpiParseError
from pid_agent.ingestion.dexpi_loader import load_plant


def by_proteus_id(graph: nx.MultiDiGraph) -> dict[str, dict]:
    return {d["proteusId"]: d for _, d in graph.nodes(data=True) if d.get("proteusId")}


def test_graphs_are_multidigraphs_with_expected_size(loaded):
    assert isinstance(loaded.plant_graph, nx.MultiDiGraph)
    assert isinstance(loaded.conceptual_graph, nx.MultiDiGraph)
    assert (loaded.plant_graph.number_of_nodes(), loaded.plant_graph.number_of_edges()) == (214, 376)
    assert (loaded.conceptual_graph.number_of_nodes(), loaded.conceptual_graph.number_of_edges()) == (36, 39)


def test_plant_graph_edges_are_structural_not_flow(loaded):
    labels = {d["label"] for *_, d in loaded.plant_graph.edges(data=True)}
    assert labels == {"composition", "reference"}


def test_p4711_and_h1007_exist_with_tags(loaded):
    nodes = by_proteus_id(loaded.plant_graph)
    assert nodes["CentrifugalPump-1"]["tagName"] == "P4711"
    assert nodes["PlateHeatExchanger-1"]["tagName"] == "H1007"
    assert "CentrifugalPump:Pump:Equipment" in nodes["CentrifugalPump-1"]["labels"]


def test_only_five_items_carry_a_tag_name(loaded):
    tags = sorted(d["tagName"] for _, d in loaded.plant_graph.nodes(data=True) if d.get("tagName"))
    assert tags == ["H1007", "H1008", "P4711", "P4712", "T4750"]


def test_equipment_types_are_discoverable(loaded):
    labels = Counter(d["label"] for _, d in loaded.conceptual_graph.nodes(data=True))
    for expected in ("CentrifugalPump", "ReciprocatingPump", "PlateHeatExchanger", "TubularHeatExchanger", "Tank"):
        assert labels[expected] == 1
    assert labels["BallValve"] == 5


def test_piping_data_lives_on_segments_and_systems(loaded):
    labels = Counter(d["label"] for _, d in loaded.plant_graph.nodes(data=True))
    assert labels["PipingNetworkSystem"] == 11
    assert labels["PipingNetworkSegment"] == 23
    assert labels["Pipe"] == 29
    nodes = by_proteus_id(loaded.plant_graph)
    assert nodes["PipingNetworkSegment-2"]["nominalDiameterRepresentation"] == "DN 80"
    assert nodes["PipingNetworkSystem-2"]["lineNumber"] == "47122"
    pipes = [d for _, d in loaded.plant_graph.nodes(data=True) if d["label"] == "Pipe"]
    assert all("nominalDiameterRepresentation" not in d and "lineNumber" not in d for d in pipes)


def test_node_ids_are_not_stable_but_proteus_ids_are(loaded):
    again = load_plant(loaded.source_file)
    assert set(again.plant_graph.nodes) != set(loaded.plant_graph.nodes)
    assert set(by_proteus_id(again.plant_graph)) == set(by_proteus_id(loaded.plant_graph))


def test_abstraction_drops_open_ended_pipes(loaded):
    """Documented pyDEXPI behaviour that the normalizer compensates for."""
    piping = [d for *_, d in loaded.conceptual_graph.edges(data=True) if d["label"] in ("Pipe", "DirectPipingConnection")]
    assert len(piping) == 27  # 29 Pipe + 2 DirectPipingConnection in the plant graph, 4 lost


def test_abstraction_copies_wrong_line_onto_a_node(loaded):
    """Why conceptual *node* piping attributes are never used: PipeTee-1 is an item of
    segment 11 on line 47126, but the conceptual node claims line 47125."""
    plant = loaded.plant_graph
    tee = next(n for n, d in plant.nodes(data=True) if d.get("proteusId") == "PipeTee-1")
    owner = next(u for u, _, e in plant.in_edges(tee, data=True) if e["attr_name"] == "items")
    system = next(u for u, _, e in plant.in_edges(owner, data=True) if e["attr_name"] == "segments")
    assert plant.nodes[system]["lineNumber"] == "47126"
    assert loaded.conceptual_graph.nodes[tee]["lineNumber"] == "47125"


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(DataFileNotFoundError, match="not found"):
        load_plant(tmp_path / "nope.xml")


def test_malformed_xml_raises_parse_error(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<PlantModel><Equipment></PlantModel")
    with pytest.raises(DexpiParseError):
        load_plant(bad)


def test_xml_without_plant_content_raises_parse_error(tmp_path):
    empty = tmp_path / "empty.xml"
    empty.write_text("<?xml version='1.0'?><NotAPlant/>")
    with pytest.raises(DexpiParseError):
        load_plant(empty)
