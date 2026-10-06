"""Compact views of tool results.

* ``compact_result`` is what the model sees: the facts, without bulk or duplication.
* ``render_evidence`` turns results into plain statements for the cautious fallback answer.

The full ToolResult is always kept in the trace; nothing is lost, only not re-sent.
"""

from __future__ import annotations

from typing import Any

from pid_agent.agent.status import Provenance, status_statement

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
# Dropped from the model's view: bookkeeping that carries no plant meaning.
ENTITY_DROP = {"identifier_origins", "in_topology", "confidence"}
META_KEEP = ("count", "max_depth", "cycle_detected", "start_is_in_cycle", "truncated_by_max_depth", "stopped_at", "shortest_path_only",
             "blocked", "blocked_reached", "path_count", "more_paths_exist", "line", "runs", "chains", "connections_without_valve")  # fmt: skip
# Kept from a computed fact: what it says and how to cite it. Its provenance stays in the trace.
DERIVED_KEEP = ("ref", "predicate", "subject", "object", "value", "qualifiers", "statement")
# Per-pipe details not needed to follow a route; get_connections / get_properties have them.
PATH_STEP_DROP = {"id", "type", "relationship", "nominalDiameterStandard", "pipingClassCode"}
# What an instrumentation link means, in words, so the model need not know DEXPI class names.
INSTRUMENTATION_MEANING = {
    "operated_valve_reference": "'from' is the actuating function that operates the valve 'to'",
    "signal_line": "'from' sends its control signal to 'to'",
    "measuring_line": "the measurement taken by 'from' is the input of 'to'",
    "sensing_location": "'from' measures at 'to'",
}


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
    for key in ("ref", "neighbor_is", "neighbor_category", "open_end"):
        if connection.get(key):
            out[key] = connection[key]
    if connection["relationship"] == "instrumentation":
        out["meaning"] = INSTRUMENTATION_MEANING[connection["connection_type"]]
        if connection.get("neighbor"):
            out["other_entity"] = _ref(connection["neighbor"]) + f" [{connection['neighbor']['type']}]"
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
    entities = []
    for e in result["entities"]:
        row = {"id": e["id"], "name": e["name"], "type": e["type"], "category": e["category"], "distance": e["distance"], "via": e["path_entities"][-2]}
        if e.get("ref"):
            row = {"ref": e["ref"], **row}
        row["through_equipment"] = e["through_equipment"]
        for key in ("terminal", "continues_beyond_max_depth"):
            if key in e:
                row[key] = e[key]
        entities.append(row)
    connections = []
    for connection in result["connections"]:
        full = compact_connection(connection)
        slim = {k: full[k] for k in ("ref", "from", "to", "lineNumber", "nominalDiameterRepresentation", "open_end", "note") if k in full}
        connections.append(slim)
    return {"entities": entities, "connections": connections}


def compact_entity(entity: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in entity.items() if k not in ENTITY_DROP}
    if out.get("identifier_kind") == "source_identifier":
        out.pop("identifier_kind")
    origins = entity.get("identifier_origins") or {}
    notes = {k: f"{o['kind']}: {o['origin']}" for k, o in origins.items() if o["kind"] != "source_identifier"}
    notes = {**out.get("identifier_notes", {}), **notes}
    # Aliases point at related objects and are worth reading; how a derived identifier was
    # composed is only repeated when it is the identifier that matched (see match_reason).
    notes = {k: v for k, v in notes.items() if v.startswith("alias")}
    if notes:
        out["identifier_notes"] = notes
    else:
        out.pop("identifier_notes", None)
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
            if item.get("ref"):
                entry = {"ref": item["ref"], **entry}
            if item["source_object_id"] != object_id:
                entry["on"] = item["source_object_id"]
            if item["scope"] not in ("own", "object", "connection"):
                entry["scope"] = item["scope"]
            if item.get("match"):
                entry["match"] = item["match"]
            found.append(entry)
        out[object_id] = {"found": found, "missing": report["missing"]}
        if report.get("missing_ref"):
            out[object_id]["missing_ref"] = report["missing_ref"]
        if report["missing"]:
            out[object_id]["available"] = report["available"]
    return out


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    """The model-facing view of a ToolResult dict."""
    out: dict[str, Any] = {"status": result["status"]}
    # Evidence ids, assigned by the agent: R<step> is this whole result, E<step>.0 its status
    # facts (not found, ambiguous, no path, where a traversal ended); rows carry their own "ref".
    for name in ("result_ref", "status_ref"):
        if result.get(name):
            out[name] = result[name]
    if result.get("message"):
        out["message"] = result["message"]
    resolution = result.get("resolution")
    if resolution and (resolution.get("ambiguous") or resolution.get("status") != "unique"):
        out["resolution"] = resolution
    if result["tool"] == "traverse":
        out.update({k: v for k, v in _traverse_view(result).items() if v})
    else:
        # get_connections repeats the queried entity; the model already has it.
        if result.get("entities") and result["tool"] != "get_connections":
            out["entities"] = [compact_entity(e) for e in result["entities"]]
        if result.get("connections"):
            out["connections"] = [compact_connection(c) for c in result["connections"]]
    if result.get("paths"):
        out["paths"] = [
            {
                **({"ref": path["ref"]} if path.get("ref") else {}),
                "length": path["length"],
                "direction": path["direction"],
                "entities": [_ref(e) for e in path["entities"]],
                **{k: path[k] for k in ("shut_off_valves", "check_valves", "relief_devices", "equipment", "blocked") if k in path},
                "steps": [
                    {"travelled": s["travelled"], **{k: v for k, v in compact_connection(s["connection"]).items() if k not in PATH_STEP_DROP}}
                    for s in path["steps"]
                ],
            }
            for path in result["paths"]
        ]
    if result.get("boundaries"):
        out["boundaries"] = [{k: v for k, v in b.items() if k != "reason"} for b in result["boundaries"]]
    if result.get("properties"):
        out["properties"] = _compact_properties(result["properties"])
    if result.get("derived"):
        out["derived"] = [{k: row[k] for k in DERIVED_KEEP if row.get(k) not in (None, {}, [])} for row in result["derived"]]
    if result.get("warnings"):
        out["warnings"] = result["warnings"]
    meta = {k: result["meta"][k] for k in META_KEEP if result.get("meta", {}).get(k) not in (None, [], False)}
    for key in ("endpoints", "endpoint_details", "unexplored_beyond_max_depth"):
        if result.get("meta", {}).get(key):
            meta[key] = result["meta"][key]
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


def render_evidence(observations: list[dict[str, Any]], limit: int = 40, provenance: Provenance | None = None) -> list[str]:
    """Plain, deterministic statements of what the tool results contain.

    With ``provenance`` a status is given in the application's fixed wording, so that a
    message repeating the model's own tool input is not shown as evidence.
    """
    lines: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        if line not in seen:
            seen.add(line)
            lines.append(line)

    for result in observations:
        tool, status = result["tool"], result["status"]
        if status in ("not_found", "ambiguous", "empty", "error") and result.get("message"):
            add(f"{tool}: {status_statement(result, provenance) if provenance is not None else result['message']}")
        for path in result.get("paths", []):
            add("path: " + " -> ".join(_ref(e) or "?" for e in path["entities"]))
            for step in path["steps"]:
                add(_connection_line(step["connection"]))
        for connection in result.get("connections", []):
            add(_connection_line(connection))
        for row in result.get("derived", []):
            add(row["statement"])
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
