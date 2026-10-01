"""GraphService: the seven generic, LLM-independent graph operations.

Every method returns a ToolResult whose ``evidence`` lists the graph facts it relied on.
The service implements graph mechanics only; deciding which results answer a question is
the caller's job.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pid_agent.graph.entity_resolver import EntityResolver, camel_tokens
from pid_agent.graph.normalizer import PlantIndex, normalize
from pid_agent.graph.traversal import DIRECTIONS, FlowGraph, Reach, TraversalOutcome
from pid_agent.ingestion.dexpi_loader import load_plant
from pid_agent.models import Connection, Entity, Evidence, ToolResult

logger = logging.getLogger(__name__)

RELATIONSHIPS = ("piping", "instrumentation", "all")
PATH_DIRECTIONS = ("downstream", "upstream", "any")
DEFAULT_MAX_DEPTH = 25
MIN_PARTIAL_PROPERTY_LENGTH = 4


def _normalize_property(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


class GraphService:
    def __init__(self, index: PlantIndex, max_depth_limit: int = DEFAULT_MAX_DEPTH) -> None:
        self._index = index
        self._resolver = EntityResolver(index.entities)
        self._flow = FlowGraph(index.connections.values())
        self._max_depth_limit = max_depth_limit

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
            result.entities.append({**entity.summary(), **match.to_dict()})
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
            if resolution.suggestions:
                result.message += " Similar identifiers exist (see resolution.suggestions); none was selected."
        elif resolution.ambiguous:
            result.status = "ambiguous"
            result.message = (
                f"'{query}' matches {len(resolution.matches)} entities and does not identify a "
                "single one. Use an entity id, or add line/type context."
            )
        return result

    def list_entities(self, entity_type: str | None = None) -> ToolResult:
        result = ToolResult(tool="list_entities", status="success", input={"entity_type": entity_type})
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
        for entity in self._index.entities.values():
            if entity.id in ids:
                result.entities.append(entity.summary())
                result.evidence.append(self._entity_evidence(entity))
        result.meta["count"] = len(result.entities)
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
    ) -> ToolResult:
        result = ToolResult(
            tool="traverse",
            status="success",
            input={"start_entity_id": start_entity_id, "direction": direction, "entity_types": entity_types, "max_depth": max_depth, "stop_at_types": stop_at_types},
        )
        if not self._check_choice(result, "direction", direction, DIRECTIONS):
            return result
        start = self._require_topology_entity(start_entity_id, result)
        if start is None:
            return result
        depth = self._clamp_depth(max_depth, result)
        wanted = self._type_filter(entity_types, "entity_types", result)
        stops = self._type_filter(stop_at_types, "stop_at_types", result)
        outcome = self._flow.bfs(
            start.id, direction, depth, stop_at=(lambda i: i in stops) if stops is not None else None  # type: ignore[arg-type]
        )
        used_connections: dict[str, Connection] = {}
        for reach in sorted(outcome.reached.values(), key=lambda r: (r.distance, r.entity_id)):
            if wanted is not None and reach.entity_id not in wanted:
                continue
            entity = self._index.entities[reach.entity_id]
            result.entities.append({**entity.summary(), **self._reach_view(reach)})
            result.evidence.append(self._path_evidence(start.id, reach))
            for connection_id in reach.connection_path:
                used_connections[connection_id] = self._index.connections[connection_id]
        for connection in used_connections.values():
            result.connections.append(self._connection_view(connection))
            result.evidence.append(self._connection_evidence(connection))
        self._add_open_ends(outcome, direction, result)
        self._traversal_meta(outcome, depth, result)
        if not result.entities:
            result.status = "empty"
            what = f" of type {entity_types}" if entity_types else ""
            result.message = f"No entities{what} found {direction} of {start.id} within depth {depth}."
        return result

    def find_path(self, source_entity_id: str, target_entity_id: str, direction: str = "downstream") -> ToolResult:
        result = ToolResult(tool="find_path", status="success", input={"source_entity_id": source_entity_id, "target_entity_id": target_entity_id, "direction": direction})
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
        outcome = self._flow.bfs(source.id, travel, self._max_depth_limit)  # type: ignore[arg-type]
        reach = outcome.reached.get(target.id)
        if reach is None:
            result.status = "empty"
            result.message = f"No {direction} piping path from {source.id} to {target.id} exists in the P&ID graph."
            if direction != "any":
                opposite = "upstream" if direction == "downstream" else "downstream"
                if target.id in self._flow.bfs(source.id, opposite, self._max_depth_limit).reached:  # type: ignore[arg-type]
                    result.warnings.append(f"A path does exist in the {opposite} direction.")
            self._chamber_warnings(outcome, result)
            return result
        steps = []
        for step in reach.steps:
            connection = self._index.connections[step.connection_id]
            steps.append({
                "from": self._entity_ref(step.from_id),
                "to": self._entity_ref(step.to_id),
                "travelled": "with_flow" if step.with_flow else "against_flow",
                "connection": self._connection_view(connection),
            })
            result.evidence.append(self._connection_evidence(connection))
        result.paths.append({"length": reach.distance, "direction": direction, "entities": [self._entity_ref(i) for i in reach.entity_path], "steps": steps})
        result.evidence.insert(0, self._path_evidence(source.id, reach))
        result.meta["shortest_path_only"] = True
        return result

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

    def _chamber_warnings(self, outcome: TraversalOutcome, result: ToolResult) -> None:
        for entity_id, entered, other, connection_id in outcome.chamber_skips:
            message = f"Did not continue through {entity_id} from {entered} to {other} via {connection_id}: these are separate chambers (sides) of the equipment."
            if message not in result.warnings:
                result.warnings.append(message)

    def _traversal_meta(self, outcome: TraversalOutcome, depth: int, result: ToolResult) -> None:
        result.meta.update({"visited_entities": outcome.visited_count, "max_depth": depth, "cycle_detected": outcome.cycle_detected, "start_is_in_cycle": outcome.returns_to_start, "truncated_by_max_depth": outcome.truncated, "stopped_at": outcome.stopped_at})
        if outcome.cycle_detected:
            result.warnings.append("The traversal met a recycle loop; each entity is reported once, at its shortest distance.")
        if outcome.truncated:
            result.warnings.append(f"Traversal stopped at max_depth={depth}; entities further away are not included.")
        self._chamber_warnings(outcome, result)

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
