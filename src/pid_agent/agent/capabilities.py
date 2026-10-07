"""What each graph operation can answer.

A question is first decomposed into requested outputs, each with a *kind* (the class of thing
asked for). This module declares, as data, which operations produce each kind. Three things
follow from the declaration, none of them from the wording of a question:

* planning: after the decomposition the model is told which operations can answer each
  requested output;
* coverage: a requested output is not answered by rows of an operation that cannot produce
  its kind (adjacency rows do not answer a boundary; a route that ignores flow direction does
  not answer what feeds or reaches what);
* completeness: when a composite analysis answers a requested output, the application takes
  every row of that analysis that belongs to the kind, so that part of the result cannot be
  left out by the model.

Kinds without a strict entry (items, count, property, adjacency, explanation, other) can be
answered by rows of any operation.
"""

from __future__ import annotations

from typing import Any

DRAWN_FLOW, TOPOLOGICAL = "drawn_flow", "topological"

# kind -> operation -> route semantics the result must have (None: any).
PRODUCERS: dict[str, dict[str, str | None]] = {
    "boundary": {"isolation_boundary": None},
    "signal_chain": {"trace_instrumentation": None},
    "line_structure": {"trace_line": None},
    # What is downstream or upstream, what feeds or reaches what: only along the drawn flow.
    "flow_reachability": {"traverse": DRAWN_FLOW, "find_path": DRAWN_FLOW},
    # Whether items are joined by piping at all: either reading shows that.
    "connectivity": {"find_path": None, "traverse": None, "get_connections": None, "trace_line": None, "isolation_boundary": None},
}
# Asked-for outputs that a P&ID does not contain. They are answered by a typed unknown.
NOT_IN_A_DRAWING = {"procedure_or_behaviour"}
# For a composite analysis: the rows of its result that together answer a kind. Sections hold
# rows read from the drawing; predicates select computed rows. Anything else in the result
# (context, closed ends, property rows) is shown only if the model cites it.
BUNDLES: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    ("isolation_boundary", "boundary"): {"predicates": ("isolation_boundary_valve", "check_valve_on_boundary", "relief_device_on_boundary", "unisolated_connection", "fully_valve_bounded", "relief_path_inside_boundary")},
    ("trace_instrumentation", "signal_chain"): {"sections": ("connections",), "predicates": ("signal_chain", "loop_measured_at", "loop_acts_on")},
    ("trace_line", "line_structure"): {"predicates": ("line_run", "line_meets_line")},
    ("find_path", "flow_reachability"): {"sections": ("paths", "status")},
    ("find_path", "connectivity"): {"sections": ("paths", "status")},
}
SEMANTICS_WORDS = {DRAWN_FLOW: "along the drawn flow direction (direction downstream or upstream)", TOPOLOGICAL: "ignoring flow direction"}


def compatible_operations(kind: str) -> list[str]:
    """Operations whose result can answer a requested output of this kind; empty when any can."""
    return [name + (f" ({SEMANTICS_WORDS[semantics]})" if semantics else "") for name, semantics in PRODUCERS.get(kind, {}).items()]


def answers(kind: str, tool: str, semantics: str | None) -> bool:
    """Whether a row of ``tool`` (with the given route semantics) can answer an output of ``kind``."""
    if kind in NOT_IN_A_DRAWING:
        return False
    if kind not in PRODUCERS:
        return True
    if tool not in PRODUCERS[kind]:
        return False
    needed = PRODUCERS[kind][tool]
    return needed is None or semantics == needed


def guidance(kind: str) -> str:
    """One line for the planner: how an output of this kind can be answered."""
    if kind in NOT_IN_A_DRAWING:
        return "A P&ID does not contain this. Name it as an unknown in submit_answer; cite facts only for what the drawing does show."
    operations = compatible_operations(kind)
    return f"Answered by a result of: {', '.join(operations)}." if operations else "Any graph operation can answer it."


def bundle(kind: str, tool: str, result: dict[str, Any]) -> list[str]:
    """Evidence ids of the rows of ``result`` that together answer ``kind``; empty if there is no bundle."""
    spec = BUNDLES.get((tool, kind))
    if spec is None:
        return []
    refs: list[str] = []
    for section in spec.get("sections", ()):
        if section == "status":
            if result.get("status") in ("not_found", "ambiguous", "empty") and result.get("status_ref"):
                refs.append(result["status_ref"])
        else:
            refs += [row["ref"] for row in result.get(section) or [] if row.get("ref")]
    refs += [row["ref"] for row in result.get("derived") or [] if row.get("ref") and row["predicate"] in spec.get("predicates", ())]
    return refs
