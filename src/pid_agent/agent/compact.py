"""Compact views of tool results.

* ``compact_result`` is what the model sees: the facts, without bulk or duplication.
* ``render_evidence`` turns results into plain statements for the cautious fallback answer.

The full ToolResult is always kept in the trace; nothing is lost, only not re-sent.
"""

from __future__ import annotations

from typing import Any

CONNECTION_PROPERTIES = (
    "lineNumber",
    "segmentNumber",
    "nominalDiameterRepresentation",
    "nominalDiameterStandard",
    "fluidCode",
    "pipingClassCode",
    "insulationType",
    "insulationThickness",
    "subTagName",
)
ENTITY_DROP = {"identifier_origins", "in_topology"}
META_KEEP = ("count", "visited_entities", "max_depth", "cycle_detected", "start_is_in_cycle", "truncated_by_max_depth", "stopped_at", "shortest_path_only")


def _ref(ref: dict[str, Any] | None) -> str | None:
    if ref is None:
        return None
    return ref["id"] if ref["name"] == ref["id"] else f"{ref['id']} ({ref['name']})"


def _nozzle(nozzle: dict[str, Any] | None) -> str | None:
    if not nozzle:
        return None
    label = nozzle.get("sub_tag") or nozzle["id"]
    return f"{label} [{nozzle['chamber_id']}]" if nozzle.get("chamber_id") else label


def compact_connection(connection: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": connection["id"],
        "from": _ref(connection.get("source")),
        "to": _ref(connection.get("target")),
        "type": connection["connection_type"],
        "relationship": connection["relationship"],
    }
    for key in ("neighbor_is", "reference_direction", "open_end"):
        if connection.get(key):
            out[key] = connection[key]
    properties = connection.get("properties", {})
    out.update({k: properties[k] for k in CONNECTION_PROPERTIES if k in properties})
    for key, name in (("source_nozzle", "from_nozzle"), ("target_nozzle", "to_nozzle")):
        if connection.get(key):
            out[name] = _nozzle(connection[key])
    note = connection.get("provenance", {}).get("note")
    if note:
        out["note"] = note
    return out


def _traverse_view(result: dict[str, Any]) -> dict[str, Any]:
    """Traversals can reach most of the plant, so they get the leanest view.

    Each entity names the entity it was reached ``via``, which encodes every path as a tree;
    each pipe keeps only its ends, line and diameter. Details remain available through
    get_connections / find_path / get_properties.
    """
    entities = [
        {"id": e["id"], "name": e["name"], "type": e["type"], "distance": e["distance"], "via": e["path_entities"][-2]}
        for e in result["entities"]
    ]
    connections = []
    for connection in result["connections"]:
        full = compact_connection(connection)
        slim = {k: full[k] for k in ("from", "to", "lineNumber", "nominalDiameterRepresentation", "open_end", "note") if k in full}
        connections.append(slim)
    return {"entities": entities, "connections": connections}


def compact_entity(entity: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in entity.items() if k not in ENTITY_DROP}
    origins = entity.get("identifier_origins") or {}
    notes = {k: f"{o['kind']}: {o['origin']}" for k, o in origins.items() if o["kind"] != "source_identifier"}
    if notes:
        out["identifier_notes"] = notes
    return out


def _compact_properties(properties: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for object_id, report in properties.items():
        if not isinstance(report, dict) or "found" not in report:
            out[object_id] = report
            continue
        found = []
        for item in report["found"]:
            entry = {"property": item["property"], "value": item["value"]}
            if item["source_object_id"] != object_id:
                entry["on"] = item["source_object_id"]
            if item["scope"] not in ("own", "object", "connection"):
                entry["scope"] = item["scope"]
            if item.get("match"):
                entry["match"] = item["match"]
            found.append(entry)
        out[object_id] = {"found": found, "missing": report["missing"]}
        if report["missing"]:
            out[object_id]["available"] = report["available"]
    return out


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    """The model-facing view of a ToolResult dict."""
    out: dict[str, Any] = {"status": result["status"]}
    if result.get("message"):
        out["message"] = result["message"]
    if result.get("resolution"):
        out["resolution"] = result["resolution"]
    if result["tool"] == "traverse":
        out.update({k: v for k, v in _traverse_view(result).items() if v})
    else:
        if result.get("entities"):
            out["entities"] = [compact_entity(e) for e in result["entities"]]
        if result.get("connections"):
            out["connections"] = [compact_connection(c) for c in result["connections"]]
    if result.get("paths"):
        out["paths"] = [
            {
                "length": path["length"],
                "direction": path["direction"],
                "entities": [_ref(e) for e in path["entities"]],
                "steps": [{"travelled": s["travelled"], **compact_connection(s["connection"])} for s in path["steps"]],
            }
            for path in result["paths"]
        ]
    if result.get("properties"):
        out["properties"] = _compact_properties(result["properties"])
    if result.get("warnings"):
        out["warnings"] = result["warnings"]
    meta = {k: result["meta"][k] for k in META_KEEP if k in result.get("meta", {})}
    if meta:
        out["meta"] = meta
    return out


def _connection_line(connection: dict[str, Any]) -> str:
    c = compact_connection(connection)
    details = ", ".join(f"{k} {c[k]}" for k in ("lineNumber", "segmentNumber", "nominalDiameterRepresentation", "fluidCode") if k in c)
    if c.get("open_end"):
        end = "source" if c["open_end"] == "source" else "destination"
        known = c["to"] if c["open_end"] == "source" else c["from"]
        return f"open-ended pipe {c['id']} at {known} ({details}); its {end} is not represented on this drawing"
    return f"{c['from']} -> {c['to']} [{c['type']}]" + (f" ({details})" if details else "")


def render_evidence(observations: list[dict[str, Any]], limit: int = 40) -> list[str]:
    """Plain, deterministic statements of what the tool results contain."""
    lines: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        if line not in seen:
            seen.add(line)
            lines.append(line)

    for result in observations:
        tool, status = result["tool"], result["status"]
        if status in ("not_found", "ambiguous", "empty", "error") and result.get("message"):
            add(f"{tool}: {result['message']}")
        for path in result.get("paths", []):
            add("path: " + " -> ".join(_ref(e) or "?" for e in path["entities"]))
            for step in path["steps"]:
                add(_connection_line(step["connection"]))
        for connection in result.get("connections", []):
            add(_connection_line(connection))
        if tool in ("find_entities", "list_entities", "traverse"):
            for entity in result.get("entities", []):
                suffix = f", distance {entity['distance']}" if "distance" in entity else ""
                add(f"{entity['id']} ({entity['name']}, {entity['type']}{suffix})")
        for object_id, report in result.get("properties", {}).items():
            if not isinstance(report, dict) or "found" not in report:
                continue
            for item in report["found"]:
                add(f"{item['source_object_id']}.{item['property']} = {item['value']}")
            if report["missing"]:
                add(f"{object_id}: not present in the P&ID: {', '.join(report['missing'])}")
    if len(lines) > limit:
        lines = lines[:limit] + [f"... and {len(lines) - limit} more evidence items (see the tool trace)"]
    return lines
