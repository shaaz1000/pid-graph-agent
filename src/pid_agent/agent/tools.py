"""The tool surface exposed to the agent: specs, argument validation and dispatch.

Tools are thin wrappers over GraphService. They never raise for bad input: every failure
comes back as a ToolResult with status "error".
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pid_agent.graph.service import GraphService
from pid_agent.models import ToolResult

logger = logging.getLogger(__name__)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindEntitiesArgs(_Args):
    query: str = Field(description="Tag, identifier, or short description, e.g. 'T4750', 'SV 104.01', 'C5 on line 47126', 'ball valve'.")
    entity_type: str | None = Field(default=None, description="Optional type filter, e.g. 'valve', 'pump', 'BallValve'.")


class ListEntitiesArgs(_Args):
    entity_type: str | None = Field(default=None, description="Type or category to list, e.g. 'pump', 'valve', 'equipment', 'line'. Omit to get the catalogue of types.")


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


class FindPathArgs(_Args):
    source_entity_id: str
    target_entity_id: str
    direction: str = Field(default="downstream", description="'downstream', 'upstream', or 'any' (ignore flow direction).")


class GetPropertiesArgs(_Args):
    ids: list[str] | str = Field(description="Entity ids, connection ids, or other object ids (segments, nozzles, chambers, MetaData-1).")
    requested_properties: list[str] | None = Field(default=None, description="Property names to look up. Omit to get every property.")


TOOL_ARGS: dict[str, type[_Args]] = {
    "find_entities": FindEntitiesArgs,
    "list_entities": ListEntitiesArgs,
    "get_entity": GetEntityArgs,
    "get_connections": GetConnectionsArgs,
    "traverse": TraverseArgs,
    "find_path": FindPathArgs,
    "get_properties": GetPropertiesArgs,
}
TOOL_DESCRIPTIONS: dict[str, str] = {
    "find_entities": (
        "Resolve a tag, identifier or short description to entities. 'ambiguous' = several "
        "entities match and none was chosen. 'not_found' may list resolution.suggestions: "
        "similar identifiers, not matches. Each match shows 'links': how many piping and "
        "instrumentation connections it has."
    ),
    "list_entities": (
        "List all entities of a type or category (supertypes work: 'valve' covers every valve "
        "class). Without arguments: the catalogue of types present."
    ),
    "get_entity": (
        "One entity: own properties, line/segment context, link counts and (optionally) "
        "nozzles, chambers and other sub-objects."
    ),
    "get_connections": (
        "ADJACENCY: only the immediate neighbours of one entity, one hop. For piping: the "
        "connecting pipe (line, segment, nominal diameter, fluid) and whether the neighbour is "
        "upstream or downstream; the neighbour is often a tee, valve or other fitting. For "
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
        "that were not crossed. Safe on recycle loops."
    ),
    "find_path": (
        "PATH: the shortest piping route between two known entities, with line and nominal "
        "diameter of every pipe on it."
    ),
    "get_properties": (
        "Property values of entities, connections, lines, segments, nozzles, chambers or "
        "'MetaData-1' (drawing data). Also searches an entity's sub-objects. Properties that "
        "do not exist in the P&ID are listed under 'missing'."
    ),
}


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


class GraphTools:
    def __init__(self, service: GraphService) -> None:
        self._service = service

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
