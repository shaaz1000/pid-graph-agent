"""The tool surface exposed to the agent: specs, argument validation and dispatch.

Tools are thin wrappers over GraphService. They never raise for bad input: every failure
comes back as a ToolResult with status "error".
"""

from __future__ import annotations

import logging
import time
from typing import Any

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pid_agent.graph.service import GraphService
from pid_agent.models import ToolResult

logger = logging.getLogger(__name__)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindEntitiesArgs(_Args):
    query: str = Field(description="Identifier or natural-language description of the entity to find. May include context such as the entity type or the line it is on.")
    entity_type: str | None = Field(default=None, description="Optional type filter, e.g. 'valve', 'pump', 'BallValve'.")


class ListEntitiesArgs(_Args):
    entity_type: str | None = Field(default=None, description="Type or category to list, e.g. 'pump', 'valve', 'equipment', 'line'. Omit to get the catalogue of types.")
    properties: list[str] | None = Field(default=None, description="Property names to return for every listed entity (read from the item, its line and its sub-objects).")
    property_filter: dict[str, str] | None = Field(default=None, description="Keep only entities whose property has this value, e.g. {\"nominalDiameterRepresentation\": \"DN 50\"}. Numbers compare as numbers.")


class GetEntityArgs(_Args):
    entity_id: str = Field(description="Entity id as returned by find_entities / list_entities.")
    include_children: bool = Field(default=False, description="Include nozzles, chambers and other sub-objects with their properties.")


class GetConnectionsArgs(_Args):
    entity_id: str
    direction: str = Field(default="both", description="'upstream', 'downstream' or 'both'. Applies to piping (process flow) only.")
    relationship: str = Field(default="all", description="'piping', 'instrumentation' or 'all'.")


class TraverseArgs(_Args):
    start_entity_id: str
    direction: str = Field(description="'downstream' (with process flow), 'upstream' (against it) or 'both'.")
    entity_types: list[str] | None = Field(default=None, description="Only report entities of these types.")
    max_depth: int | None = Field(default=None, description="Maximum number of connections to follow.")
    stop_at_types: list[str] | None = Field(default=None, description="Do not continue past entities of these types (they are still reported).")
    blocked_entity_ids: list[str] | None = Field(default=None, description="Entities to treat as closed: the search does not enter or pass them. Use it for 'what is still reachable if these are shut'.")


class FindPathArgs(_Args):
    source_entity_id: str
    target_entity_id: str
    direction: str = Field(default="downstream", description="'downstream', 'upstream', or 'any' (ignore flow direction).")
    all_paths: bool = Field(default=False, description="Return every route that visits no entity twice, not only the shortest.")
    blocked_entity_ids: list[str] | None = Field(default=None, description="Entities to treat as closed: no route may pass them.")


class GetPropertiesArgs(_Args):
    ids: list[str] | str = Field(description="Entity ids, connection ids, or ids of other objects (segments, nozzles, chambers, the drawing metadata object).")
    requested_properties: list[str] | None = Field(default=None, description="Property names to look up. Omit to get every property.")


class IsolationBoundaryArgs(_Args):
    entity_id: str = Field(description="The item to isolate: equipment, or any item on the piping.")


class TraceInstrumentationArgs(_Args):
    entity_id: str = Field(description="Any member of a loop: the measured item, a sensor, a controller, an actuating function or the operated valve.")


class TraceLineArgs(_Args):
    line: str = Field(description="A line number, or the id of a piping line.")


UNKNOWN_CATEGORIES = Literal[
    "operating_procedure",   # a sequence or method of operation, e.g. the order in which to close valves
    "operating_state",       # what is open, closed, running or flowing now
    "process_behaviour",     # how pressure, flow, level or temperature would respond
    "design_adequacy",       # whether something is sufficient or safe, e.g. relief sizing
    "off_drawing",           # what lies beyond an off-page connector or an open-ended pipe
    "not_represented",       # an item or attribute the question asks for that the drawing does not have
    "purpose_or_intent",     # why something is there, what it protects against
    "ambiguous_request",     # the question does not identify a single item
    "other",
]


OUTPUT_KINDS = Literal["items", "count", "property", "connection_or_route", "boundary", "ordering_or_procedure", "consequence", "explanation", "other"]


class RequestedOutput(_Args):
    description: str = Field(max_length=200, description="One thing the question asks to be told, in a few words.")
    kind: OUTPUT_KINDS = Field(default="other", description="What sort of output it is.")


class DecomposeRequestArgs(_Args):
    requested_outputs: list[RequestedOutput] = Field(min_length=1, max_length=8, description="Every separate thing the question asks to be told, one entry each, in the order asked.")


class CitedFact(_Args):
    ref: str = Field(description="An evidence id: E<step>.<n> for one row, R<step> for all rows of a result.")
    covers: list[str] = Field(default_factory=list, description="Ids of the requested outputs (q1, q2, ...) this evidence answers.")


class Unknown(_Args):
    category: UNKNOWN_CATEGORIES
    covers: list[str] = Field(default_factory=list, description="Ids of the requested outputs (q1, q2, ...) that the P&ID does not establish.")
    about: list[str] = Field(default_factory=list, description="The items this concerns, if any: entity ids, tags or names from the tool results.")
    note: str = Field(default="", max_length=300, description="Optional, for the run log only: what exactly was asked. It is not shown in the answer; the category says what the P&ID does not establish.")


class SubmitAnswerArgs(_Args):
    direct_facts: list[CitedFact] = Field(default_factory=list, description="Rows that state what is in the drawing: items, properties, connections, instrumentation links.")
    derived_facts: list[CitedFact] = Field(default_factory=list, description="Rows computed by a graph operation: reachability, routes, boundaries, signal chains, runs of a line.")
    unknowns: list[Unknown] = Field(default_factory=list, description="What the question asks for that the P&ID does not establish.")
    summary: str | None = Field(default=None, max_length=400, description="Optional, for the run log only. It is not shown to the user and is not part of the answer.")

    @field_validator("direct_facts", "derived_facts", mode="before")
    @classmethod
    def _bare_ids(cls, value: Any) -> Any:
        """A bare evidence id is accepted as a cited fact that names no requested output."""
        return [{"ref": item} if isinstance(item, str) else item for item in value] if isinstance(value, list) else value


TOOL_ARGS: dict[str, type[_Args]] = {
    "find_entities": FindEntitiesArgs,
    "list_entities": ListEntitiesArgs,
    "get_entity": GetEntityArgs,
    "get_connections": GetConnectionsArgs,
    "traverse": TraverseArgs,
    "find_path": FindPathArgs,
    "get_properties": GetPropertiesArgs,
    "isolation_boundary": IsolationBoundaryArgs,
    "trace_instrumentation": TraceInstrumentationArgs,
    "trace_line": TraceLineArgs,
}
SUBMIT_ANSWER = "submit_answer"
DECOMPOSE_REQUEST = "decompose_request"
DECOMPOSE_DESCRIPTION = (
    "Call this first, before any graph tool. List every separate thing the question asks to be "
    "told, one entry each. Do not answer and do not judge whether the drawing can answer it: "
    "this only records what was asked. Each entry gets an id (q1, q2, ...) that the final "
    "answer must account for."
)
TOOL_DESCRIPTIONS: dict[str, str] = {
    "find_entities": (
        "Find entities by identifier, type or description, optionally with context such as "
        "the line they are on. 'ambiguous' = several "
        "entities match and none was chosen. 'not_found' may list resolution.suggestions: "
        "similar identifiers, not matches. Each match shows 'links': how many piping and "
        "instrumentation connections it has."
    ),
    "list_entities": (
        "List all entities of a type or category (supertypes work: 'valve' covers every valve "
        "class). Without arguments: the catalogue of types present. With properties: the "
        "named property values of every listed entity in one call. With property_filter: only "
        "the entities whose property has the given value, which finds an item described by a "
        "property."
    ),
    "get_entity": (
        "One entity: own properties, line/segment context, link counts and (optionally) "
        "nozzles, chambers and other sub-objects."
    ),
    "get_connections": (
        "ADJACENCY: only the immediate neighbours of one entity, one hop. For piping: the "
        "connecting pipe (line, segment, nominal diameter, fluid) and whether the neighbour is "
        "upstream or downstream. neighbor_category says what the neighbour is: a "
        "piping_component (tee, valve, reducer, connector) is an intermediate item the piping "
        "passes through, not the equipment at the far end; use traverse to go beyond it. For "
        "instrumentation: the linked instrument function and what the link means. open_end = "
        "the pipe exists but its other end is not on this drawing."
    ),
    "traverse": (
        "REACHABILITY: everything reachable from an entity along piping, any number of hops, "
        "in one call ('downstream' = drawn flow direction, 'upstream', or 'both'). Each result "
        "has its distance, the entity it was reached via, through_equipment (equipment lying "
        "between it and the start; empty = reached through pipes, valves and fittings only) "
        "and terminal (nothing further is drawn in that direction). An entity with "
        "continues_beyond_max_depth is not an end: the search stopped there because of "
        "max_depth and what lies beyond was not explored. meta.endpoints lists all terminal "
        "entities even when entity_types filters them out. boundaries lists chamber boundaries "
        "that were not crossed. Safe on recycle loops. The search follows the piping through "
        "intermediate tees, valves and fittings. With stop_at_types it stops on each branch at "
        "the first entity of those types, which gives the nearest such items in that direction. "
        "meta.endpoint_details says for every terminal entity whether it is a drawing_end (an "
        "off-page connector: the piping continues on another drawing, destination not shown) "
        "or simply end_of_drawn_piping."
    ),
    "find_path": (
        "PATH: the shortest piping route between two known entities, with line and nominal "
        "diameter of every pipe on it. By default only the shortest route is returned, which "
        "answers 'is there a route' but says nothing about other routes. Use all_paths when the "
        "question is about alternatives: whether more than one route exists, which routes "
        "there are, or what a route depends on. Every route then lists the shut-off valves, "
        "check valves, relief devices and equipment on it. With blocked_entity_ids: the routes "
        "that remain when those entities are treated as closed; no route is a result too. "
        "direction 'any' ignores the drawn flow direction; each step says whether it runs with "
        "or against it."
    ),
    "get_properties": (
        "Property values of entities, connections, lines, segments, nozzles, chambers or the "
        "drawing metadata object (its id is listed by list_entities without arguments). Also "
        "searches an entity's sub-objects. Properties that do not exist in the P&ID are listed "
        "under 'missing'."
    ),
    "isolation_boundary": (
        "BOUNDARY: follows the piping away from one item in every direction, through fittings, "
        "to the nearest valve on each branch. Returns the shut-off valves that bound the item, "
        "check valves and relief devices met before any shut-off valve, every connection that "
        "has no valve before it reaches other equipment or leaves the drawing, and two "
        "summary facts: whether the item is fully bounded by valves, and whether a relief "
        "device stays connected inside that boundary. Drawn topology only."
    ),
    "trace_instrumentation": (
        "LOOP: every instrumentation link connected to an item, in signal order, in one call: "
        "where the measurement is taken, each function the signal passes, the actuating "
        "function with its encoded fail action, the operated valve and the line it is on. "
        "Start from any member of the loop."
    ),
    "trace_line": (
        "LINE: one piping line as runs between junctions in drawn flow direction: where each "
        "run starts and ends, what lies on it, its sizes, how it ends, and where the line "
        "meets other lines."
    ),
}
SUBMIT_DESCRIPTION = (
    "Give the final answer. Cite the evidence rows that answer the question; the application "
    "writes the answer from them. direct_facts are rows read from the drawing, derived_facts "
    "are rows computed by a graph operation, unknowns name by category what the question asks "
    "for that the P&ID does not establish. No text you write is shown to the user."
)


def _simplify_schema(node: Any) -> Any:
    """Drop pydantic noise so the schema is small and portable across providers."""
    if isinstance(node, list):
        return [_simplify_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {k: _simplify_schema(v) for k, v in node.items() if k != "title"}
    options = node.get("anyOf")
    if options:
        concrete = [o for o in options if o.get("type") != "null"]
        if len(concrete) == 1 and len(options) == 2:  # Optional[X] -> X that may be null
            node.pop("anyOf")
            node = {**concrete[0], **node, "type": [concrete[0]["type"], "null"]}
    return node


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace $ref pointers by the definitions they name: some providers do not follow them."""
    definitions = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(definitions[node["$ref"].rsplit("/", 1)[-1]])
        return {k: walk(v) for k, v in node.items()}

    return walk(schema)


def tool_specs() -> list[dict[str, Any]]:
    """Provider-neutral tool definitions (name, description, JSON-schema parameters)."""
    return [
        {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "parameters": _simplify_schema(args.model_json_schema()),
        }
        for name, args in TOOL_ARGS.items()
    ]


def decompose_request_spec() -> dict[str, Any]:
    """The first action of a structured run: what the question asks for, recorded before any lookup."""
    return {"name": DECOMPOSE_REQUEST, "description": DECOMPOSE_DESCRIPTION, "parameters": _simplify_schema(_inline_refs(DecomposeRequestArgs.model_json_schema()))}


def requested_outputs(arguments: dict[str, Any]) -> tuple[list[dict[str, str]], str | None]:
    """The requested outputs with ids assigned by code, or the reason the arguments are unusable."""
    try:
        args = DecomposeRequestArgs(**arguments)
    except ValidationError as exc:
        return [], "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return [{"id": f"q{number}", "description": item.description.strip(), "kind": item.kind} for number, item in enumerate(args.requested_outputs, start=1)], None


def submit_answer_spec() -> dict[str, Any]:
    """The final-answer action. It is validated by the agent, not executed on the graph."""
    return {"name": SUBMIT_ANSWER, "description": SUBMIT_DESCRIPTION, "parameters": _simplify_schema(_inline_refs(SubmitAnswerArgs.model_json_schema()))}


class GraphTools:
    def __init__(self, service: GraphService) -> None:
        self._service = service
        self._graph_names: frozenset[str] | None = None

    def graph_names(self) -> frozenset[str]:
        """Every id, name, tag, identifier, type and line number in the graph, lower-cased.

        Used to decide whether a value may be shown as graph data. Compared whole, never searched.
        """
        if self._graph_names is None:
            index, names = self._service.index, set()
            for entity in index.entities.values():
                names.update([entity.id, entity.name, entity.tag or "", entity.type, entity.category, *entity.type_hierarchy, *entity.identifiers.values(), *(c.id for c in entity.children)])
            names.update(index.objects)
            for connection in index.connections.values():
                names.update([connection.id, str(connection.properties.get("lineNumber") or "")])
            self._graph_names = frozenset(" ".join(str(n).split()).casefold() for n in names if n)
        return self._graph_names

    def resolve_entity(self, text: str) -> list[tuple[str, str]]:
        """(id, name) of the entities an id, tag or name denotes: one, several, or none."""
        entities = self._service.index.entities
        if text in entities:
            return [(text, entities[text].name)]
        return [(i, entities[i].name) for i in self._service.resolver.resolve(str(text)).entity_ids]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        started = time.perf_counter()
        arguments = arguments or {}
        result = self._dispatch(name, arguments)
        result.meta["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        logger.info("tool_call tool=%s status=%s duration_ms=%s", name, result.status, result.meta["duration_ms"])
        return result

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in TOOL_ARGS:
            return ToolResult(tool=name, status="error", input=arguments, message=f"Unknown tool '{name}'. Available tools: {', '.join(TOOL_ARGS)}.")
        if not isinstance(arguments, dict):
            return ToolResult(tool=name, status="error", message="Tool arguments must be a JSON object.")
        try:
            args = TOOL_ARGS[name](**arguments)
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            return ToolResult(tool=name, status="error", input=arguments, message=f"Invalid arguments for {name}: {problems}")
        try:
            return getattr(self._service, name)(**args.model_dump())
        except Exception as exc:  # a tool must never take the agent down
            logger.exception("tool_failed tool=%s", name)
            return ToolResult(tool=name, status="error", input=arguments, message=f"{name} failed: {type(exc).__name__}: {exc}")
