"""GraphService: the generic, LLM-independent graph operations.

Every method returns a ToolResult whose ``evidence`` lists the graph facts it relied on.
The service implements graph mechanics only; deciding which results answer a question is
the caller's job.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pid_agent.graph import analysis
from pid_agent.graph.entity_resolver import EntityResolver, camel_tokens
from pid_agent.graph.normalizer import PlantIndex, normalize
from pid_agent.graph.traversal import DIRECTIONS, FlowGraph, Reach, TraversalOutcome
from pid_agent.ingestion.dexpi_loader import load_plant
from pid_agent.models import Connection, Entity, Evidence, ToolResult

logger = logging.getLogger(__name__)

RELATIONSHIPS = ("piping", "instrumentation", "all")
PATH_DIRECTIONS = ("downstream", "upstream", "any")
# What a route or a reach result means. "drawn_flow": it follows the drawn flow direction
# (downstream, or upstream against it), so it can support a statement about what feeds or
# reaches what. "topological": flow direction was ignored, so it shows only that the items
# are connected by piping.
DRAWN_FLOW, TOPOLOGICAL = "drawn_flow", "topological"
ROUTE_SEMANTICS = {"downstream": DRAWN_FLOW, "upstream": DRAWN_FLOW, "any": TOPOLOGICAL, "both": TOPOLOGICAL}
ONE_WAY_ROLES = ("check_valve", "relief_device")  # devices that pass flow in their drawn direction only
DEFAULT_MAX_DEPTH = 25
MAX_PATHS = 12
MIN_PARTIAL_PROPERTY_LENGTH = 4


def _normalize_property(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _number_and_unit(text: str) -> tuple[float, str] | None:
    """(84.0, "kw") for "84 kW" or "84.0kW"; None when the text does not start with a number."""
    text = str(text).strip()
    end = 0
    while end < len(text) and (text[end].isdigit() or text[end] in ".-+"):
        end += 1
    try:
        return float(text[:end]), "".join(text[end:].split()).casefold()
    except ValueError:
        return None


def same_value(actual: Any, wanted: Any) -> bool:
    """Equal ignoring case and spacing; numbers compare as numbers when the units agree."""
    a, b = _number_and_unit(actual), _number_and_unit(wanted)
    if a is not None and b is not None:
        return a[0] == b[0] and (a[1] == b[1] or not b[1])
    return "".join(str(actual).split()).casefold() == "".join(str(wanted).split()).casefold()


class GraphService:
    def __init__(self, index: PlantIndex, max_depth_limit: int = DEFAULT_MAX_DEPTH) -> None:
        self._index = index
        self._resolver = EntityResolver(index.entities)
        self._flow = FlowGraph(index.connections.values())
        self._max_depth_limit = max_depth_limit
        self.piping = analysis.PipingIndex(index.connections)

    @classmethod
    def from_file(cls, xml_file: Path | str, max_depth_limit: int = DEFAULT_MAX_DEPTH) -> GraphService:
        return cls(normalize(load_plant(xml_file)), max_depth_limit)

    @property
    def index(self) -> PlantIndex:
        return self._index

    @property
    def resolver(self) -> EntityResolver:
        return self._resolver

    # ============================================================== tools
    def find_entities(self, query: str, entity_type: str | None = None) -> ToolResult:
        result = ToolResult(tool="find_entities", status="success", input={"query": query, "entity_type": entity_type})
        resolution = self._resolver.resolve(query, entity_type)
        result.warnings += resolution.warnings
        for match in resolution.matches:
            entity = self._index.entities[match.entity_id]
            result.entities.append({**entity.summary(), **match.to_dict(), "links": self._link_counts(entity.id)})
            result.evidence.append(self._entity_evidence(entity))
        result.resolution = {
            "status": resolution.status,
            "ambiguous": resolution.ambiguous,
            "match_count": len(resolution.matches),
            "suggestions": resolution.suggestions,
        }
        if not resolution.matches:
            result.status = "not_found"
            result.message = f"No entity in the P&ID graph matches '{query}'."
            text = (query or "").strip()
            if text in self._index.connections:
                link = self._index.connections[text]
                result.message = (
                    f"'{text}' is a {link.relationship} connection ({link.connection_type}) from "
                    f"{link.source} to {link.target}, not an entity. Use get_connections on either "
                    "end, or get_properties with this id."
                )
            elif text in self._index.objects and text not in self._index.entities:
                record = self._index.objects[text]
                owner = f" of {record.owner_entity_id}" if record.owner_entity_id else ""
                result.message = f"'{text}' is a {record.type} sub-object{owner}, not an entity. Use get_properties with this id."
            if resolution.suggestions:
                result.message += " Similar identifiers exist (see resolution.suggestions); none was selected."
        elif resolution.ambiguous:
            result.status = "ambiguous"
            result.message = (
                f"'{query}' matches {len(resolution.matches)} entities and does not identify a "
                "single one. Use an entity id, or add line/type context."
            )
        return result

    def list_entities(self, entity_type: str | None = None, properties: list[str] | None = None, property_filter: dict[str, Any] | None = None) -> ToolResult:
        result = ToolResult(tool="list_entities", status="success", input={"entity_type": entity_type, "properties": properties, "property_filter": property_filter})
        if not entity_type:
            result.properties = {
                "types": self._resolver.type_catalogue(),
                "categories": self._category_counts(),
                "other_objects": [o.id for o in self._index.objects.values() if o.type == "MetaData"],
            }
            result.message = "No entity_type given: returning the catalogue of types present in the graph."
            return result
        ids = self._resolver.entities_of_type(entity_type)
        if ids is None:
            result.status = "empty"
            result.message = f"'{entity_type}' is not a type present in the P&ID graph."
            result.properties = {"types": self._resolver.type_catalogue()}
            return result
        wanted = [*(properties or []), *[n for n in (property_filter or {}) if n not in (properties or [])]]
        for entity in self._index.entities.values():
            if entity.id not in ids:
                continue
            row = entity.summary()
            if wanted:
                # Requested attributes, read from the item, its line context and its sub-objects.
                found = self._property_report(self._property_sources(entity.id, result)[1], wanted)["found"]  # type: ignore[index]
                if any(not any(_normalize_property(i["property"]) == _normalize_property(name) and same_value(i["value"], value) for i in found) for name, value in (property_filter or {}).items()):
                    continue
                # Each value with the object that carries it, when that is a sub-object or the line.
                row["attributes"] = [{"property": i["property"], "value": i["value"], **({"on": i["source_object_id"]} if i["source_object_id"] != entity.id else {})} for i in found]
                for item in found:
                    result.evidence.append(Evidence(kind="property", id=f"{item['source_object_id']}.{item['property']}", source_graph="plant_graph", source_object_ids=[item["source_object_id"]],
                                                    fact={"object_id": item["source_object_id"], "property": item["property"], "value": item["value"], "scope": item["scope"]}))  # fmt: skip
            result.entities.append(row)
            result.evidence.append(self._entity_evidence(entity))
        result.meta["count"] = len(result.entities)
        if not result.entities:
            result.status = "empty"
            result.message = f"No '{entity_type}' has {property_filter}."
        return result

    def get_entity(self, entity_id: str, include_children: bool = False) -> ToolResult:
        result = ToolResult(tool="get_entity", status="success", input={"entity_id": entity_id, "include_children": include_children})
        entity = self._require_entity(entity_id, result)
        if entity is None:
            return result
        detail = entity.model_dump(exclude={"children"}, exclude_none=True)
        if include_children:
            detail["children"] = [c.model_dump() for c in entity.children]
        else:
            detail["children_available"] = [{"id": c.id, "type": c.type} for c in entity.children]
        detail["links"] = self._link_counts(entity.id)
        result.entities.append(detail)
        result.evidence.append(self._entity_evidence(entity, with_properties=True))
        if include_children:
            for child in entity.children:
                result.evidence.append(
                    Evidence(kind="entity", id=child.id, fact={"type": child.type, "part_of": entity.id, **child.properties}, source_graph="plant_graph", source_object_ids=[child.id])
                )
        return result

    def get_connections(self, entity_id: str, direction: str = "both", relationship: str = "all") -> ToolResult:
        result = ToolResult(tool="get_connections", status="success", input={"entity_id": entity_id, "direction": direction, "relationship": relationship})
        if not self._check_choice(result, "direction", direction, DIRECTIONS):
            return result
        if not self._check_choice(result, "relationship", relationship, RELATIONSHIPS):
            return result
        entity = self._require_topology_entity(entity_id, result)
        if entity is None:
            return result
        for connection in self._index.connections.values():
            if entity.id not in (connection.source, connection.target):
                continue
            if relationship != "all" and connection.relationship != relationship:
                continue
            is_source = connection.source == entity.id
            view = self._connection_view(connection)
            neighbour = connection.target if is_source else connection.source
            view["neighbor"] = self._entity_ref(neighbour)
            if neighbour is not None:
                # equipment, piping_component (valve, fitting, connector) or instrumentation
                view["neighbor_category"] = self._index.entities[neighbour].category
            if connection.relationship == "piping":
                side = "downstream" if is_source else "upstream"
                if direction not in ("both", side):
                    continue
                view["neighbor_is"] = side
            else:
                view["reference_direction"] = "outgoing" if is_source else "incoming"
            result.connections.append(view)
            result.evidence.append(self._connection_evidence(connection))
        self._warn_open_ends(result)
        if relationship != "piping" and direction != "both" and any(c["relationship"] == "instrumentation" for c in result.connections):
            result.warnings.append(
                "Instrumentation connections are not process flow; the direction filter was "
                "applied to piping connections only."
            )
        if not result.connections:
            result.status = "empty"
            result.message = f"{entity.id} has no {relationship if relationship != 'all' else ''} connections in direction '{direction}'.".replace("  ", " ")
        result.entities.append(entity.summary())
        return result

    def traverse(
        self,
        start_entity_id: str,
        direction: str,
        entity_types: list[str] | None = None,
        max_depth: int | None = None,
        stop_at_types: list[str] | None = None,
        blocked_entity_ids: list[str] | None = None,
    ) -> ToolResult:
        result = ToolResult(
            tool="traverse",
            status="success",
            input={"start_entity_id": start_entity_id, "direction": direction, "entity_types": entity_types, "max_depth": max_depth, "stop_at_types": stop_at_types},
        )
        if blocked_entity_ids:
            result.input["blocked_entity_ids"] = blocked_entity_ids
        if not self._check_choice(result, "direction", direction, DIRECTIONS):
            return result
        start = self._require_topology_entity(start_entity_id, result)
        if start is None:
            return result
        depth = self._clamp_depth(max_depth, result)
        wanted = self._type_filter(entity_types, "entity_types", result)
        stops = self._type_filter(stop_at_types, "stop_at_types", result)
        blocked = self._blocked(blocked_entity_ids, result, start.id)
        if blocked is None:
            return result
        outcome = self._flow.bfs(
            start.id, direction, depth, stop_at=(lambda i: i in stops) if stops is not None else None, blocked=blocked  # type: ignore[arg-type]
        )
        used_connections: dict[str, Connection] = {}
        endpoints: list[str] = []
        for reach in sorted(outcome.reached.values(), key=lambda r: (r.distance, r.entity_id)):
            terminal = direction != "both" and not self._flow.has_moves(reach.entity_id, direction)  # type: ignore[arg-type]
            if terminal:
                endpoints.append(reach.entity_id)
            if wanted is not None and reach.entity_id not in wanted:
                continue
            entity = self._index.entities[reach.entity_id]
            row = {**entity.summary(), **self._reach_view(reach), "route_semantics": ROUTE_SEMANTICS[direction]}
            # Path facts that separate "reached directly" from "reached through other equipment".
            row["through_equipment"] = [i for i in reach.entity_path[1:-1] if self._index.entities[i].category == "equipment"]
            if terminal:
                row["terminal"] = True
            elif reach.entity_id in outcome.frontier:
                # Cut off by max_depth, not an end: the graph goes on from here.
                row["terminal"] = False
                row["continues_beyond_max_depth"] = True
            result.entities.append(row)
            result.evidence.append(self._path_evidence(start.id, reach))
            for connection_id in reach.connection_path:
                used_connections[connection_id] = self._index.connections[connection_id]
        for connection in used_connections.values():
            result.connections.append(self._connection_view(connection))
            result.evidence.append(self._connection_evidence(connection))
        self._add_open_ends(outcome, direction, result)
        self._traversal_meta(outcome, depth, result)
        # Entities where nothing further is drawn in the travel direction; listed even when
        # entity_types filters them out of the main result.
        result.meta["endpoints"] = endpoints
        # What kind of end each one is: an off-page connector is where the piping leaves this
        # drawing; anything else is simply the last item drawn on that branch.
        result.meta["endpoint_details"] = [
            {**self._entity_ref(i), "category": self._index.entities[i].category, "kind": "drawing_end" if "OffPageConnector" in self._index.entities[i].type else "end_of_drawn_piping"}
            for i in endpoints
        ]
        # Entities where the search stopped only because of max_depth (also unfiltered).
        result.meta["unexplored_beyond_max_depth"] = sorted(outcome.frontier - {start.id})
        result.meta["start"] = start.id
        result.meta["route_semantics"] = ROUTE_SEMANTICS[direction]
        if blocked:
            # A hypothetical: these items were treated as closed. Nothing is said about the process.
            result.meta["blocked"] = sorted(blocked)
            result.meta["blocked_reached"] = outcome.blocked_at
        if not result.entities:
            result.status = "empty"
            what = f" of type {entity_types}" if entity_types else ""
            result.message = f"No entities{what} found {direction} of {start.id} within depth {depth}."
        return result

    def find_path(self, source_entity_id: str, target_entity_id: str, direction: str = "downstream", all_paths: bool = False, blocked_entity_ids: list[str] | None = None) -> ToolResult:
        result = ToolResult(tool="find_path", status="success", input={"source_entity_id": source_entity_id, "target_entity_id": target_entity_id, "direction": direction})
        if all_paths:
            result.input["all_paths"] = True
        if blocked_entity_ids:
            result.input["blocked_entity_ids"] = blocked_entity_ids
        if not self._check_choice(result, "direction", direction, PATH_DIRECTIONS):
            return result
        source = self._require_topology_entity(source_entity_id, result)
        target = self._require_topology_entity(target_entity_id, result) if source else None
        if source is None or target is None:
            return result
        if source.id == target.id:
            result.status = "error"
            result.message = "Source and target are the same entity."
            return result
        for entity in (source, target):
            if entity.id not in self._flow:
                result.warnings.append(f"{entity.id} ({entity.type}) has no piping connections, so it cannot be on a piping path. Use get_connections to see its instrumentation links.")
        travel = "both" if direction == "any" else direction
        blocked = self._blocked(blocked_entity_ids, result, source.id, target.id)
        if blocked is None:
            return result
        closed = f" with {', '.join(sorted(blocked))} treated as closed" if blocked else ""
        outcome = self._flow.bfs(source.id, travel, self._max_depth_limit, blocked=blocked)  # type: ignore[arg-type]
        reach = outcome.reached.get(target.id)
        if blocked:
            result.meta["blocked"] = sorted(blocked)
        result.meta["route_semantics"] = ROUTE_SEMANTICS[travel]
        if reach is None:
            result.status = "empty"
            result.message = f"No {direction} piping path from {source.id} to {target.id} exists in the P&ID graph{closed}."
            result.meta["no_path"] = {"source": source.id, "target": target.id, "direction": direction, "route_semantics": ROUTE_SEMANTICS[travel], **({"blocked": sorted(blocked)} if blocked else {})}
            if direction != "any" and not blocked:
                opposite = "upstream" if direction == "downstream" else "downstream"
                if target.id in self._flow.bfs(source.id, opposite, self._max_depth_limit).reached:  # type: ignore[arg-type]
                    result.warnings.append(f"A path does exist in the {opposite} direction.")
            self._chamber_boundaries(outcome, direction, result)
            return result
        routes, cut_short = self._flow.simple_paths(source.id, target.id, travel, self._max_depth_limit, MAX_PATHS, blocked) if all_paths else ([reach.steps], False)  # type: ignore[arg-type]
        for route in routes:
            found = Reach(target.id, len(route), route)
            steps = []
            for step in route:
                connection = self._index.connections[step.connection_id]
                steps.append({
                    "from": self._entity_ref(step.from_id),
                    "to": self._entity_ref(step.to_id),
                    "travelled": "with_flow" if step.with_flow else "against_flow",
                    "connection": self._connection_view(connection),
                })
                result.evidence.append(self._connection_evidence(connection))
            path = {"length": found.distance, "direction": direction, "route_semantics": ROUTE_SEMANTICS[travel], "entities": [self._entity_ref(i) for i in found.entity_path], "steps": steps}
            if path["route_semantics"] == TOPOLOGICAL:
                # How far this is from a flow route: pipes followed against the drawn flow, and
                # one-way devices (check valves, relief devices) passed against their direction.
                against = [step for step in route if not step.with_flow]
                path["pipes_against_flow"] = len(against)
                reversed_devices = [i for step in against for i in (step.from_id, step.to_id) if analysis.piping_role(self._index.entities[i]) in ONE_WAY_ROLES]
                if reversed_devices:
                    path["one_way_devices_against_flow"] = list(dict.fromkeys(reversed_devices))
            # What lies on the route, by kind, so that routes can be told apart.
            for role, name in (("isolation_valve", "shut_off_valves"), ("check_valve", "check_valves"), ("relief_device", "relief_devices"), ("equipment", "equipment")):
                on_route = [i for i in found.entity_path[1:-1] if analysis.piping_role(self._index.entities[i]) == role]
                if on_route:
                    path[name] = on_route
            if blocked:
                path["blocked"] = sorted(blocked)
            result.paths.append(path)
        result.evidence.insert(0, self._path_evidence(source.id, reach))
        result.meta["shortest_path_only"] = not all_paths
        if all_paths:
            result.meta["path_count"] = len(routes)
            result.meta["more_paths_exist"] = cut_short
        return result

    def isolation_boundary(self, entity_id: str) -> ToolResult:
        return analysis.isolation_boundary(self, entity_id)

    def trace_instrumentation(self, entity_id: str) -> ToolResult:
        return analysis.trace_instrumentation(self, entity_id)

    def trace_line(self, line: str) -> ToolResult:
        return analysis.trace_line(self, line)

    def get_properties(self, ids: list[str] | str, requested_properties: list[str] | None = None) -> ToolResult:
        id_list = [ids] if isinstance(ids, str) else list(ids)
        result = ToolResult(tool="get_properties", status="success", input={"ids": id_list, "requested_properties": requested_properties})
        any_found = False
        for object_id in id_list:
            sources = self._property_sources(object_id, result)
            if sources is None:
                result.properties[object_id] = {"error": "not_found"}
                continue
            resolved_id, entries = sources
            report = self._property_report(entries, requested_properties)
            result.properties[resolved_id] = report
            any_found |= bool(report["found"])
            for item in report["found"]:
                result.evidence.append(
                    Evidence(kind="property", id=f"{item['source_object_id']}.{item['property']}", fact={"object_id": item["source_object_id"], "property": item["property"], "value": item["value"], "scope": item["scope"]}, source_graph="plant_graph", source_object_ids=[item["source_object_id"]])
                )
        if all("error" in report for report in result.properties.values()):
            result.status = "not_found"
            result.message = "None of the given ids exists in the P&ID graph."
        elif not any_found:
            result.status = "empty"
            result.message = "The requested properties are not present in the P&ID graph for these objects."
        return result

    # ============================================================ helpers
    def _link_counts(self, entity_id: str) -> dict[str, int]:
        """How many connections of each kind an entity has, so callers know what to ask for."""
        counts = {"piping_upstream": 0, "piping_downstream": 0, "open_ended_pipes": 0, "instrumentation": 0}
        for connection in self._index.connections.values():
            if entity_id not in (connection.source, connection.target):
                continue
            if connection.relationship == "instrumentation":
                counts["instrumentation"] += 1
            elif connection.open_end:
                counts["open_ended_pipes"] += 1
            elif connection.source == entity_id:
                counts["piping_downstream"] += 1
            else:
                counts["piping_upstream"] += 1
        return {k: v for k, v in counts.items() if v}

    def _category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entity in self._index.entities.values():
            counts[entity.category] = counts.get(entity.category, 0) + 1
        return counts

    @staticmethod
    def _check_choice(result: ToolResult, name: str, value: str, allowed: tuple[str, ...]) -> bool:
        if value in allowed:
            return True
        result.status = "error"
        result.message = f"Unsupported {name} '{value}'. Use one of: {', '.join(allowed)}."
        return False

    def _require_entity(self, entity_id: str, result: ToolResult) -> Entity | None:
        """Look up by id; fall back to deterministic resolution of a unique identifier."""
        entity = self._index.entities.get(entity_id)
        if entity is not None:
            return entity
        resolution = self._resolver.resolve(str(entity_id))
        if resolution.status == "unique":
            entity = self._index.entities[resolution.entity_ids[0]]
            result.warnings.append(f"'{entity_id}' is not an entity id; resolved it to {entity.id} ({resolution.matches[0].reason}).")
            # The caller used a tag or other identifier: record which entity it denotes.
            result.evidence.append(self._entity_evidence(entity))
            return entity
        if resolution.status == "multiple":
            result.status = "ambiguous"
            result.message = f"'{entity_id}' matches several entities; pass one entity id."
            result.entities = [self._index.entities[i].summary() for i in resolution.entity_ids]
        else:
            result.status = "not_found"
            result.message = f"No entity '{entity_id}' exists in the P&ID graph."
            result.resolution = {"status": "none", "suggestions": resolution.suggestions}
        return None

    def _require_topology_entity(self, entity_id: str, result: ToolResult) -> Entity | None:
        entity = self._require_entity(entity_id, result)
        if entity is not None and not entity.in_topology:
            result.status = "error"
            result.message = (
                f"{entity.id} is a {entity.type} (a piping line), not a node in the connection "
                "topology. Use get_entity with include_children=true to see its segments, "
                "components and connections."
            )
            return None
        return entity

    def _blocked(self, ids: list[str] | None, result: ToolResult, *ends: str) -> frozenset[str] | None:
        """Entity ids to treat as closed, or None (with the error set) if one is unusable."""
        blocked: set[str] = set()
        for item in ids or []:
            entity = self._require_topology_entity(item, result)
            if entity is None:
                return None
            if entity.id in ends:
                result.status = "error"
                result.message = f"{entity.id} is an end of the search and cannot also be blocked."
                return None
            blocked.add(entity.id)
        return frozenset(blocked)

    def _clamp_depth(self, max_depth: int | None, result: ToolResult) -> int:
        if max_depth is None:
            return self._max_depth_limit
        depth = max(1, min(int(max_depth), self._max_depth_limit))
        if depth != max_depth:
            result.warnings.append(f"max_depth {max_depth} was clamped to {depth} (allowed 1..{self._max_depth_limit}).")
        return depth

    def _type_filter(self, types: list[str] | None, name: str, result: ToolResult) -> set[str] | None:
        if not types:
            return None
        ids: set[str] = set()
        for phrase in types:
            matched = self._resolver.entities_of_type(phrase)
            if matched is None:
                result.warnings.append(f"{name}: '{phrase}' is not a type present in the graph (call list_entities without arguments to see the types).")
            else:
                ids |= matched
        return ids

    def _entity_ref(self, entity_id: str | None) -> dict[str, Any] | None:
        if entity_id is None:
            return None
        entity = self._index.entities[entity_id]
        return {"id": entity.id, "name": entity.name, "type": entity.type}

    def _connection_view(self, connection: Connection) -> dict[str, Any]:
        view = connection.model_dump(exclude_none=True)
        view["source"] = self._entity_ref(connection.source)
        view["target"] = self._entity_ref(connection.target)
        if connection.relationship == "piping":
            view["flow"] = "source_to_target"
        return view

    @staticmethod
    def _reach_view(reach: Reach) -> dict[str, Any]:
        return {"distance": reach.distance, "path_entities": reach.entity_path, "path_connections": reach.connection_path}

    def _entity_evidence(self, entity: Entity, with_properties: bool = False) -> Evidence:
        fact: dict[str, Any] = {"type": entity.type, "name": entity.name, **entity.identifiers}
        if with_properties:
            fact["properties"] = entity.properties
            if entity.piping_context:
                fact["piping_context"] = entity.piping_context
        return Evidence(kind="entity", id=entity.id, fact=fact, source_graph="plant_graph", source_object_ids=[entity.id])

    @staticmethod
    def _connection_evidence(connection: Connection) -> Evidence:
        fact = {"source": connection.source, "target": connection.target, "relationship": connection.relationship, "connection_type": connection.connection_type, **connection.properties}
        return Evidence(
            kind="open_end" if connection.open_end else "connection",
            id=connection.id,
            fact=fact,
            source_graph=connection.provenance.derived_from,
            source_object_ids=connection.provenance.source_object_ids,
        )

    @staticmethod
    def _path_evidence(start_id: str, reach: Reach) -> Evidence:
        return Evidence(kind="path", id=f"{start_id}->{reach.entity_id}", fact={"entities": reach.entity_path, "connections": reach.connection_path, "distance": reach.distance}, source_graph="conceptual_graph", source_object_ids=reach.connection_path)

    @staticmethod
    def _warn_open_ends(result: ToolResult) -> None:
        count = sum(1 for c in result.connections if c.get("open_end"))
        if count:
            result.warnings.append(
                f"{count} connection(s) are open-ended: the pipe exists in the DEXPI model but its "
                "other end is not represented on this drawing, so no neighbour can be stated."
            )

    def _add_open_ends(self, outcome: TraversalOutcome, direction: str, result: ToolResult) -> None:
        """Report open-ended pipes that the traversal ran into in its travel direction."""
        for connection in self._index.connections.values():
            if not connection.open_end:
                continue
            leaves_drawing = connection.open_end == "target"
            if direction != "both" and leaves_drawing != (direction == "downstream"):
                continue
            entity_id = connection.source if leaves_drawing else connection.target
            chambers = outcome.chambers_at(entity_id) if entity_id else set()
            if not chambers:
                continue
            nozzle = connection.source_nozzle if leaves_drawing else connection.target_nozzle
            nozzle_chamber = nozzle.chamber_id if nozzle else None
            if entity_id != outcome.start and nozzle_chamber and None not in chambers and nozzle_chamber not in chambers:
                continue
            result.connections.append(self._connection_view(connection))
            result.evidence.append(self._connection_evidence(connection))
        self._warn_open_ends(result)

    def _chamber_boundaries(self, outcome: TraversalOutcome, direction: str, result: ToolResult) -> None:
        """Record each chamber boundary the traversal respected: as a structured, graph-derived
        fact with evidence, and as a readable warning."""
        for entity_id, entered, other, connection_id in outcome.chamber_skips:
            boundary = {
                "type": "chamber_boundary",
                "equipment": entity_id,
                "entered_chamber": entered,
                "blocked_chamber": other,
                "blocked_connection": connection_id,
                "direction": direction,
                "reason": "the path entered the equipment through one chamber; the blocked connection attaches to a different chamber (another side of the equipment)",
            }
            if boundary in result.boundaries:
                continue
            result.boundaries.append(boundary)
            result.evidence.append(
                Evidence(
                    kind="boundary",
                    id=f"{entity_id}:{entered}|{other}",
                    fact=boundary,
                    source_graph="plant_graph",
                    source_object_ids=[entity_id, entered, other, connection_id],
                )
            )
            result.warnings.append(
                f"Did not continue through {entity_id} from {entered} to {other} via {connection_id}: these are separate chambers (sides) of the equipment."
            )

    def _traversal_meta(self, outcome: TraversalOutcome, depth: int, result: ToolResult) -> None:
        result.meta.update({"visited_entities": outcome.visited_count, "max_depth": depth, "cycle_detected": outcome.cycle_detected, "start_is_in_cycle": outcome.returns_to_start, "truncated_by_max_depth": outcome.truncated, "stopped_at": outcome.stopped_at})
        if outcome.cycle_detected:
            result.warnings.append("The traversal met a recycle loop; each entity is reported once, at its shortest distance.")
        if outcome.truncated:
            result.warnings.append(f"Traversal stopped at max_depth={depth}; entities further away are not included.")
        self._chamber_boundaries(outcome, str(result.input.get("direction")), result)

    def _property_sources(self, object_id: str, result: ToolResult) -> tuple[str, list[tuple[str, Any, str, str]]] | None:
        """Return (resolved id, [(property, value, source_object_id, scope)])."""
        index = self._index
        if object_id in index.connections:
            connection = index.connections[object_id]
            return object_id, [(k, v, connection.properties.get("segment_id") or object_id, "connection") for k, v in connection.properties.items()]
        if object_id not in index.entities and object_id in index.objects:
            record = index.objects[object_id]
            return object_id, [(k, v, object_id, "object") for k, v in record.properties.items()]
        probe = ToolResult(tool="get_properties", status="success")
        entity = self._require_entity(object_id, probe)
        result.warnings += probe.warnings
        result.evidence += probe.evidence
        if entity is None:
            result.warnings.append(probe.message or f"Unknown id '{object_id}'.")
            return None
        entries = [(k, v, entity.id, "own") for k, v in entity.properties.items()]
        context = entity.piping_context or {}
        entries += [(k, v, context["segment_id"], "owning_segment") for k, v in context.items() if k not in ("segment_id", "line_id")]
        for child in entity.children:
            entries += [(k, v, child.id, f"child:{child.type}") for k, v in child.properties.items()]
        return entity.id, entries

    @staticmethod
    def _property_report(entries: list[tuple[str, Any, str, str]], requested: list[str] | None) -> dict[str, Any]:
        def item(entry: tuple[str, Any, str, str], match: str | None = None) -> dict[str, Any]:
            name, value, source, scope = entry
            out = {"property": name, "value": value, "source_object_id": source, "scope": scope}
            if match:
                out["match"] = match
            return out

        available = sorted({name for name, *_ in entries})
        if not requested:
            return {"found": [item(e) for e in entries], "missing": [], "available": available}
        found: list[dict[str, Any]] = []
        missing: list[str] = []
        for name in requested:
            key = _normalize_property(name)
            exact = [item(e) for e in entries if _normalize_property(e[0]) == key]
            partial = []
            if not exact and len(key) >= MIN_PARTIAL_PROPERTY_LENGTH:
                words = set(camel_tokens(name))
                partial = [
                    item(e, f"partial match for '{name}'")
                    for e in entries
                    if key in _normalize_property(e[0]) or (words and words <= set(camel_tokens(e[0])))
                ]
            if exact or partial:
                found += exact or partial
            else:
                missing.append(name)
        return {"found": found, "missing": missing, "available": available}
