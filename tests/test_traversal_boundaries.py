"""Traversal boundaries: chamber boundaries as structured evidence, and the difference
between a real end of the drawn piping and a search that was merely cut off by max_depth."""

from __future__ import annotations

import json

import pytest

from pid_agent.agent.compact import compact_result
from pid_agent.agent.grounding import check_grounding
from pid_agent.graph.traversal import FlowGraph
from test_traversal import chain, pipe

# (start, direction) pairs whose traversal runs into the chamber boundary inside H1008.
THROUGH_EXCHANGER = [("ReciprocatingPump-1", "downstream"), ("Tank-1", "downstream"), ("PipeTee-4", "downstream")]


# ============================================== A. chamber boundaries as evidence
@pytest.mark.parametrize(("start", "direction"), THROUGH_EXCHANGER)
def test_chamber_boundary_is_a_structured_fact_with_evidence(service, index, start, direction):
    result = service.traverse(start, direction)
    (boundary,) = result.boundaries
    assert boundary == {
        "type": "chamber_boundary",
        "equipment": "TubularHeatExchanger-1",
        "entered_chamber": "Chamber-3",
        "blocked_chamber": "Chamber-4",
        "blocked_connection": "PipingNetworkSegment-23/connections/1",
        "direction": direction,
        "reason": boundary["reason"],
    }
    (evidence,) = [e for e in result.evidence if e.kind == "boundary"]
    assert evidence.fact == boundary and evidence.source_graph == "plant_graph"
    assert evidence.source_object_ids == ["TubularHeatExchanger-1", "Chamber-3", "Chamber-4", "PipingNetworkSegment-23/connections/1"]
    known = set(index.entities) | set(index.connections) | set(index.objects)
    assert set(evidence.source_object_ids) <= known  # every id is a real graph object
    # The facts agree with the graph: the blocked pipe leaves the exchanger from the other chamber.
    blocked = index.connections[boundary["blocked_connection"]]
    assert blocked.source == boundary["equipment"] and blocked.source_nozzle.chamber_id == boundary["blocked_chamber"]


def test_no_boundary_is_reported_when_none_was_met(service):
    assert service.traverse("CentrifugalPump-1", "upstream").boundaries == []
    assert service.traverse("TubularHeatExchanger-1", "downstream", max_depth=1).boundaries == []  # starting there follows both sides


def test_find_path_reports_the_boundary_that_blocked_it(service):
    result = service.find_path("PipeTee-4", "GlobeValve-3")
    assert result.status == "empty" and result.boundaries[0]["blocked_chamber"] == "Chamber-4"
    assert [e.kind for e in result.evidence] == ["boundary"]


def test_boundary_survives_compaction_without_prose(tools):
    seen = compact_result(tools.call("traverse", {"start_entity_id": "Tank-1", "direction": "downstream", "entity_types": ["equipment"]}).to_dict())
    assert seen["boundaries"] == [{
        "type": "chamber_boundary", "equipment": "TubularHeatExchanger-1", "entered_chamber": "Chamber-3",
        "blocked_chamber": "Chamber-4", "blocked_connection": "PipingNetworkSegment-23/connections/1", "direction": "downstream",
    }]


@pytest.fixture(scope="module")
def through_exchanger(tools):
    return [tools.call("traverse", {"start_entity_id": "CentrifugalPump-1", "direction": "downstream", "entity_types": ["equipment"]}).to_dict()]


@pytest.mark.parametrize(
    "answer",
    [
        "The route does not continue from Chamber-3 to Chamber-4 of TubularHeatExchanger-1.",
        "The connection PipingNetworkSegment-23/connections/1 was not followed.",
        "Flow entering chamber Chamber-3 cannot leave through chamber Chamber-4.",
        # the shape of the answer that was wrongly withheld in the diagnostic run
        "Reachable equipment: H1007 (distance 1), T4750 (3), P4712 (8), H1008 (14). The traversal "
        "did not continue through TubularHeatExchanger-1 from Chamber-3 to Chamber-4 via "
        "PipingNetworkSegment-23/connections/1, because those are separate sides of the exchanger. "
        "Nothing further is drawn beyond BallValve-2, BlindFlange-1, BlindFlange-2 and FlowOutPipeOffPageConnector-1.",
    ],
)
def test_boundary_identifiers_ground_claims(through_exchanger, answer):
    report = check_grounding(answer, "What can the fluid reach?", through_exchanger)
    assert report.grounded, report.unsupported


@pytest.mark.parametrize(
    ("answer", "claim"),
    [
        ("It is blocked at segment Chamber-4.", "segment Chamber-4"),
        ("It is blocked at nozzle Chamber-4.", "nozzle Chamber-4"),
        ("It is blocked on line PipingNetworkSegment-23/connections/1.", "line PipingNetworkSegment-23/connections/1"),
        ("The blocked connection Chamber-4 is on the utility side.", "connection Chamber-4"),
        ("The path stops in chamber PipingNetworkSegment-23/connections/1.", "chamber PipingNetworkSegment-23/connections/1"),
    ],
)
def test_boundary_identifiers_cannot_play_another_role(through_exchanger, answer, claim):
    report = check_grounding(answer, "q", through_exchanger)
    assert [c["claim"] for c in report.unsupported] == [claim]
    assert report.unsupported[0]["kind"] == "identifier_role"


def test_other_chambers_are_not_grounded_by_the_boundary(through_exchanger):
    report = check_grounding("The path is blocked at Chamber-9.", "q", through_exchanger)
    assert [c["claim"] for c in report.unsupported] == ["Chamber-9"]


def test_warning_text_alone_is_still_not_evidence(through_exchanger):
    """Strip the structured facts and keep only the prose: the identifiers stop being grounded."""
    prose_only = [{**through_exchanger[0], "boundaries": [], "evidence": [e for e in through_exchanger[0]["evidence"] if e["kind"] != "boundary"]}]
    assert any("Chamber-4" in w for w in prose_only[0]["warnings"])
    report = check_grounding("The route does not continue into Chamber-4.", "q", prose_only)
    assert [c["claim"] for c in report.unsupported] == ["Chamber-4"]


def test_user_text_echoed_in_a_warning_cannot_ground_a_claim(tools):
    result = tools.call("traverse", {"start_entity_id": "CentrifugalPump-1", "direction": "downstream", "entity_types": ["XQ-999 unit"]}).to_dict()
    assert any("XQ-999" in w for w in result["warnings"])
    assert "XQ-999" not in json.dumps(result["boundaries"]) + json.dumps(result["evidence"])
    report = check_grounding("The pump feeds XQ-999.", "q", [result])
    assert [c["claim"] for c in report.unsupported] == ["XQ-999"]


# ======================================= B. terminal versus truncated frontier
def rows(result):
    return {e["id"]: e for e in result.entities}


# (start, direction, depth, entities cut off by the depth limit, entities that really end)
CUT_OFF = [
    ("ReciprocatingPump-1", "downstream", 4, {"BallValve-3", "BallValve-4", "Tank-1"}, {"BallValve-2"}),
    ("CentrifugalPump-1", "downstream", 2, {"GlobeValve-2"}, set()),
    ("Tank-1", "upstream", 1, {"GlobeValve-1", "GlobeValve-2", "SpringLoadedGlobeSafetyValve-1"}, set()),
    ("PipeTee-3", "downstream", 2, {"PipeTee-4"}, {"BlindFlange-1"}),
]


@pytest.mark.parametrize(("start", "direction", "depth", "cut_off", "ends"), CUT_OFF)
def test_depth_limit_marks_a_frontier_not_an_end(service, start, direction, depth, cut_off, ends):
    result = service.traverse(start, direction, max_depth=depth)
    found = rows(result)
    assert result.meta["truncated_by_max_depth"] is True
    assert {i for i, e in found.items() if e.get("continues_beyond_max_depth")} == cut_off
    assert set(result.meta["unexplored_beyond_max_depth"]) == cut_off
    assert {i for i, e in found.items() if e.get("terminal") is True} == ends == set(result.meta["endpoints"])
    for entity_id in cut_off:
        assert found[entity_id]["terminal"] is False  # explicitly not an end
        assert found[entity_id]["distance"] == depth
        assert entity_id not in result.meta["endpoints"]


@pytest.mark.parametrize(("start", "direction", "depth", "cut_off", "ends"), CUT_OFF)
def test_frontier_entities_really_do_continue(service, start, direction, depth, cut_off, ends):
    """Going one step deeper reaches something new from every frontier entity."""
    shallow = set(rows(service.traverse(start, direction, max_depth=depth)))
    deeper = rows(service.traverse(start, direction, max_depth=depth + 1))
    for entity_id in cut_off:
        assert any(e["path_entities"][-2] == entity_id for i, e in deeper.items() if i not in shallow)


def test_complete_traversal_has_ends_but_no_frontier(service):
    result = service.traverse("ReciprocatingPump-1", "downstream")
    assert result.meta["truncated_by_max_depth"] is False and result.meta["unexplored_beyond_max_depth"] == []
    assert not any("continues_beyond_max_depth" in e for e in result.entities)
    assert {i for i, e in rows(result).items() if e.get("terminal")} == {"BallValve-2", "BlindFlange-1", "BlindFlange-2", "FlowOutPipeOffPageConnector-1"}


def test_frontier_is_reported_even_when_a_type_filter_hides_the_rows(service):
    result = service.traverse("ReciprocatingPump-1", "downstream", entity_types=["equipment"], max_depth=4)
    assert [e["id"] for e in result.entities] == ["Tank-1"]
    assert set(result.meta["unexplored_beyond_max_depth"]) == {"BallValve-3", "BallValve-4", "Tank-1"}


def test_frontier_and_chamber_boundary_are_reported_independently(service):
    """BallValve-4 > PipeTee-4 > H1008 at depth 2: the exchanger's same-chamber outlet is
    unexplored (frontier), while its other chamber is a boundary, not unexplored territory."""
    result = service.traverse("BallValve-4", "downstream", max_depth=2)
    exchanger = rows(result)["TubularHeatExchanger-1"]
    assert exchanger["continues_beyond_max_depth"] is True and exchanger["terminal"] is False
    assert [b["blocked_chamber"] for b in result.boundaries] == ["Chamber-4"]
    deeper = rows(service.traverse("BallValve-4", "downstream", max_depth=3))
    assert "GlobeValve-1" in deeper and "GlobeValve-3" not in deeper  # only the same chamber continues


@pytest.mark.parametrize(("start", "direction", "depth", "cut_off", "ends"), CUT_OFF)
def test_frontier_and_truncation_survive_compaction(tools, start, direction, depth, cut_off, ends):
    seen = compact_result(tools.call("traverse", {"start_entity_id": start, "direction": direction, "max_depth": depth}).to_dict())
    assert seen["meta"]["truncated_by_max_depth"] is True and seen["meta"]["max_depth"] == depth
    assert set(seen["meta"]["unexplored_beyond_max_depth"]) == cut_off
    assert set(seen["meta"].get("endpoints", [])) == ends
    found = {e["id"]: e for e in seen["entities"]}
    for entity_id in cut_off:
        assert found[entity_id]["terminal"] is False and found[entity_id]["continues_beyond_max_depth"] is True
    for entity_id in ends:
        assert found[entity_id]["terminal"] is True and "continues_beyond_max_depth" not in found[entity_id]
    for row in found.values():
        assert "through_equipment" in row


def test_frontier_on_a_small_branching_graph():
    """A -> B -> C -> D and B -> E: at depth 2, C is cut off (D lies beyond) and E is a real end."""
    graph = FlowGraph([*chain("A", "B", "C", "D"), pipe("B", "E")])
    outcome = graph.bfs("A", "downstream", 2)
    assert outcome.truncated and outcome.frontier == {"C"}
    assert not graph.has_moves("E", "downstream") and graph.has_moves("C", "downstream")
    assert graph.bfs("A", "downstream", 3).frontier == set()


def test_revisiting_a_known_entity_at_the_limit_is_not_a_frontier():
    graph = FlowGraph(chain("A", "B", "A"))  # a loop that closes exactly at the limit
    outcome = graph.bfs("A", "downstream", 1)
    assert outcome.frontier == set() and not outcome.truncated
