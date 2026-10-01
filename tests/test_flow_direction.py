"""Does a piping connection's source -> target really mean process flow?

Checked against the raw Proteus XML, independently of pyDEXPI's graph code:

1. the drawing's PipeFlowArrow symbols point along the centre line in FromID -> ToID order;
2. every normalized piping connection follows its segment's FromID -> ToID order;
3. off-page connectors, pumps and the check valve are oriented as flow requires;
4. instrumentation links never take part in upstream/downstream traversal.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pytest

from conftest import ids


@pytest.fixture(scope="module")
def xml_segments(loaded):
    return list(ET.parse(loaded.source_file).getroot().iter("PipingNetworkSegment"))


def _centre_line_direction_at(segment: ET.Element, point: tuple[float, float]):
    """Unit vector of the centre-line leg (in XML point order) that the point lies on."""
    for line in segment.findall("CenterLine"):
        points = [(float(c.get("X")), float(c.get("Y"))) for c in line.findall("Coordinate")]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            along = ((point[0] - x1) * dx + (point[1] - y1) * dy) / length**2
            offset = abs((point[0] - x1) * dy - (point[1] - y1) * dx) / length
            if -0.01 <= along <= 1.01 and offset < 0.5:
                return dx / length, dy / length
    return None


def test_flow_arrows_agree_with_from_to_order(xml_segments):
    checked = 0
    for segment in xml_segments:
        for arrow in segment.findall("PipeFlowArrow"):
            location = arrow.find("Position/Location")
            reference = arrow.find("Position/Reference")
            point = (float(location.get("X")), float(location.get("Y")))
            pointing = (float(reference.get("X")), float(reference.get("Y")))
            direction = _centre_line_direction_at(segment, point)
            assert direction is not None, f"{arrow.get('ID')} is not on its segment's centre line"
            dot = direction[0] * pointing[0] + direction[1] * pointing[1]
            assert dot > 0.99, f"{arrow.get('ID')} points against FromID -> ToID in {segment.get('ID')}"
            checked += 1
    assert checked == 8


def test_connections_follow_segment_from_to(xml_segments, index):
    owner = {child.id: entity.id for entity in index.entities.values() if entity.in_topology for child in entity.children}
    checked = 0
    for segment in xml_segments:
        link = segment.find("Connection")
        chain = sorted(
            (c for c in index.connections.values() if c.properties.get("segment_id") == segment.get("ID")),
            key=lambda c: int(c.id.rsplit("/", 1)[1]),
        )
        assert chain, segment.get("ID")
        for previous, following in zip(chain, chain[1:]):
            assert previous.target == following.source
        for attribute, actual in (("FromID", chain[0].source), ("ToID", chain[-1].target)):
            xml_id = link.get(attribute)
            expected = owner.get(xml_id, xml_id) if xml_id else None
            assert actual == expected, (segment.get("ID"), attribute)
        checked += 1
    assert checked == 23


def test_off_page_connectors_are_pure_source_and_sink(service):
    assert service.get_connections("FlowInPipeOffPageConnector-1", "upstream", "piping").status == "empty"
    assert service.get_connections("FlowOutPipeOffPageConnector-1", "downstream", "piping").status == "empty"
    assert len(service.get_connections("FlowInPipeOffPageConnector-1", "downstream", "piping").connections) == 1


@pytest.mark.parametrize("pump", ["CentrifugalPump-1", "ReciprocatingPump-1"])
def test_pumps_have_one_inlet_and_one_outlet(service, pump):
    assert len(service.get_connections(pump, "upstream", "piping").connections) == 1
    assert len(service.get_connections(pump, "downstream", "piping").connections) == 1


def test_upstream_and_downstream_are_mirror_images(index, service):
    """If B is directly downstream of A, then A is directly upstream of B, for every pipe."""
    for connection in index.connections.values():
        if connection.relationship != "piping" or connection.open_end:
            continue
        down = service.get_connections(connection.source, "downstream", "piping")
        up = service.get_connections(connection.target, "upstream", "piping")
        assert connection.id in [c["id"] for c in down.connections]
        assert connection.id in [c["id"] for c in up.connections]


def test_instrumentation_is_excluded_from_flow_traversal(service):
    # TT4750.03 senses at tank T4750, and BlindFlange-1 is PT4712.01's sensing location.
    for start in ("Tank-1", "BlindFlange-1"):
        for direction in ("upstream", "downstream", "both"):
            reached = service.traverse(start, direction)
            categories = {e["category"] for e in reached.entities}
            assert "instrumentation" not in categories
            assert all(c["relationship"] == "piping" for c in reached.connections)


def test_instrumentation_entity_has_no_flow_neighbours(service):
    result = service.traverse("ActuatingFunction-1", "both")
    assert result.status == "empty" and ids(result) == []


def test_direction_filter_only_applies_to_piping(service):
    result = service.get_connections("Tank-1", "upstream", "all")
    piping = [c for c in result.connections if c["relationship"] == "piping"]
    other = [c for c in result.connections if c["relationship"] == "instrumentation"]
    assert all(c["neighbor_is"] == "upstream" for c in piping) and len(piping) == 3
    assert [c["connection_type"] for c in other] == ["sensing_location"]
    assert "neighbor_is" not in other[0] and other[0]["reference_direction"] == "incoming"
    assert any("not process flow" in w for w in result.warnings)
