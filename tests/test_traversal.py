"""Traversal mechanics on small hand-built flow graphs.

These graphs exist only to exercise the algorithm (cycles, depth, chambers). Everything
about the real plant is tested against C01 in the other test modules.
"""

from __future__ import annotations

from pid_agent.graph.traversal import FlowGraph
from pid_agent.models import Connection, NozzleRef, Provenance

PROVENANCE = Provenance(derived_from="conceptual_graph", present_in_conceptual_graph=True)


def pipe(source, target, *, out_chamber=None, in_chamber=None, relationship="piping"):
    return Connection(
        id=f"{source}>{target}",
        source=source,
        target=target,
        relationship=relationship,
        connection_type="pipe" if relationship == "piping" else "signal_line",
        source_nozzle=NozzleRef(id=f"n-{source}-out", chamber_id=out_chamber) if out_chamber else None,
        target_nozzle=NozzleRef(id=f"n-{target}-in", chamber_id=in_chamber) if in_chamber else None,
        provenance=PROVENANCE,
    )


def chain(*names):
    return [pipe(a, b) for a, b in zip(names, names[1:])]


def test_downstream_and_upstream_are_opposites():
    graph = FlowGraph(chain("A", "B", "C"))
    assert list(graph.bfs("A", "downstream", 10).reached) == ["B", "C"]
    assert list(graph.bfs("C", "upstream", 10).reached) == ["B", "A"]
    assert graph.bfs("A", "upstream", 10).reached == {}
    assert graph.bfs("C", "downstream", 10).reached == {}


def test_distance_and_path_are_reported():
    reach = FlowGraph(chain("A", "B", "C")).bfs("A", "downstream", 10).reached["C"]
    assert reach.distance == 2
    assert reach.entity_path == ["A", "B", "C"]
    assert reach.connection_path == ["A>B", "B>C"]
    assert all(step.with_flow for step in reach.steps)


def test_upstream_steps_are_marked_against_flow():
    reach = FlowGraph(chain("A", "B")).bfs("B", "upstream", 10).reached["A"]
    assert reach.entity_path == ["B", "A"] and not reach.steps[0].with_flow


def test_cycle_terminates_and_is_flagged():
    graph = FlowGraph(chain("A", "B", "C", "A"))
    outcome = graph.bfs("A", "downstream", 50)
    assert set(outcome.reached) == {"B", "C"}
    assert outcome.cycle_detected and outcome.returns_to_start
    assert not outcome.truncated


def test_cycle_not_through_start():
    graph = FlowGraph([*chain("S", "A", "B", "A")])
    outcome = graph.bfs("S", "downstream", 50)
    assert set(outcome.reached) == {"A", "B"}
    assert outcome.cycle_detected and not outcome.returns_to_start


def test_shortest_distance_wins_when_two_routes_exist():
    graph = FlowGraph([*chain("A", "B", "C", "D"), pipe("A", "D")])
    assert graph.bfs("A", "downstream", 10).reached["D"].distance == 1


def test_max_depth_bounds_the_search_and_flags_truncation():
    graph = FlowGraph(chain("A", "B", "C", "D"))
    outcome = graph.bfs("A", "downstream", 2)
    assert list(outcome.reached) == ["B", "C"] and outcome.truncated
    assert not graph.bfs("A", "downstream", 3).truncated


def test_stop_at_reports_the_node_but_does_not_pass_it():
    graph = FlowGraph(chain("A", "B", "C", "D"))
    outcome = graph.bfs("A", "downstream", 10, stop_at=lambda n: n == "C")
    assert list(outcome.reached) == ["B", "C"] and outcome.stopped_at == ["C"]


def test_stop_at_does_not_apply_to_the_start():
    graph = FlowGraph(chain("A", "B"))
    assert list(graph.bfs("A", "downstream", 10, stop_at=lambda n: True).reached) == ["B"]


def test_both_ignores_direction():
    graph = FlowGraph([pipe("A", "B"), pipe("C", "B")])
    outcome = graph.bfs("A", "both", 10)
    assert set(outcome.reached) == {"B", "C"} and not outcome.cycle_detected


def test_disconnected_node_is_not_reached():
    graph = FlowGraph([pipe("A", "B"), pipe("X", "Y")])
    assert "Y" not in graph.bfs("A", "both", 10).reached


def test_instrumentation_and_open_ends_are_not_part_of_the_flow_graph():
    signal = pipe("A", "B", relationship="instrumentation")
    open_end = Connection(id="open", source="A", target=None, relationship="piping", connection_type="open_end", open_end="target", provenance=PROVENANCE)
    graph = FlowGraph([signal, open_end])
    assert "A" not in graph and graph.bfs("A", "both", 10).reached == {}


def test_path_does_not_cross_between_chambers():
    # HX has a shell side (in from A, out to B) and a tube side (out to C).
    graph = FlowGraph([
        pipe("A", "HX", in_chamber="shell"),
        pipe("HX", "B", out_chamber="shell"),
        pipe("HX", "C", out_chamber="tube"),
    ])
    outcome = graph.bfs("A", "downstream", 10)
    assert set(outcome.reached) == {"HX", "B"}
    assert outcome.chamber_skips == [("HX", "shell", "tube", "HX>C")]


def test_starting_at_equipment_follows_every_chamber():
    graph = FlowGraph([pipe("HX", "B", out_chamber="shell"), pipe("HX", "C", out_chamber="tube")])
    assert set(graph.bfs("HX", "downstream", 10).reached) == {"B", "C"}


def test_nozzle_without_chamber_does_not_block():
    graph = FlowGraph([pipe("A", "T", in_chamber="c1"), pipe("T", "B")])
    assert set(graph.bfs("A", "downstream", 10).reached) == {"T", "B"}


def test_equipment_reached_through_both_chambers_expands_both():
    graph = FlowGraph([
        pipe("S", "HX", in_chamber="shell"),
        pipe("HX", "B", out_chamber="shell"),
        pipe("B", "HX", in_chamber="tube"),  # comes back into the other side
        pipe("HX", "C", out_chamber="tube"),
    ])
    assert set(graph.bfs("S", "downstream", 10).reached) == {"HX", "B", "C"}
