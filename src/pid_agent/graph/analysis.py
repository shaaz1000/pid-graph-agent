"""Graph analyses: questions that need many hops, answered by one deterministic operation.

    isolation_boundary     the region around an item up to the nearest valves, and what is not valved
    trace_instrumentation  every instrumentation link of a loop, in signal order
    trace_line             one piping line as runs between junctions, with its branches

Results carry ``derived`` rows: typed facts computed by an algorithm, each with the operation,
its parameters and the graph objects it was computed from. The operations describe drawn
topology only. They never say what a valve position, a trip or a closure does to the process.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from pid_agent.graph.entity_resolver import normalize_identifier
from pid_agent.models import Connection, Entity, Evidence, ToolResult

if TYPE_CHECKING:
    from pid_agent.graph.service import GraphService

# What an item is for the piping around it, read from its DEXPI class hierarchy.
ROLE_BY_CLASS = (
    ("OperatedValve", "isolation_valve"),
    ("CheckValve", "check_valve"),
    ("SafetyValveOrFitting", "relief_device"),
    ("PipeOffPageConnector", "off_page_connector"),
)
LINE_PROPERTIES = ("lineNumber", "nominalDiameterRepresentation")
# The order in which a signal passes an instrumentation link; a sensing location is recorded
# from the sensor to the place it measures, so it is read backwards.
SIGNAL_ORDER_REVERSED = {"sensing_location"}


def piping_role(entity: Entity) -> str:
    for dexpi_class, role in ROLE_BY_CLASS:
        if dexpi_class in entity.type_hierarchy:
            return role
    return "equipment" if entity.category == "equipment" else "fitting"


class PipingIndex:
    """Every piping connection at each item, open-ended ones included."""

    def __init__(self, connections: dict[str, Connection]) -> None:
        self.at: dict[str, list[Connection]] = {}
        for connection in connections.values():
            if connection.relationship != "piping":
                continue
            for end in (connection.source, connection.target):
                if end is not None:
                    self.at.setdefault(end, []).append(connection)

    def degree(self, entity_id: str) -> int:
        return len(self.at.get(entity_id, []))


def label(service: GraphService, entity_id: str | None) -> str:
    if entity_id is None:
        return "a point not represented on this drawing"
    entity = service.index.entities[entity_id]
    return entity.id if entity.name == entity.id else f"{entity.name} ({entity.id})"


def add_derived(result: ToolResult, predicate: str, subject: str, statement: str, *, operation: str, parameters: dict[str, Any], object: str | None = None,
                value: Any = None, entities: list[str] | None = None, connections: list[str] | None = None, **qualifiers: Any) -> dict[str, Any]:  # fmt: skip
    """Append one computed fact. ``statement`` is its wording, written by code."""
    row: dict[str, Any] = {"predicate": predicate, "subject": subject}
    if object is not None:
        row["object"] = object
    if value is not None:
        row["value"] = value
    row["qualifiers"] = {k: v for k, v in qualifiers.items() if v not in (None, "", [], {})}
    row.update({"statement": statement, "operation": operation, "parameters": parameters, "source_entities": entities or [], "source_connections": connections or []})
    result.derived.append(row)
    result.evidence.append(
        Evidence(kind="derived", id=f"{operation}:{predicate}:{subject}:{object or value}", fact={k: row[k] for k in ("predicate", "subject", "object", "value", "qualifiers", "operation", "parameters") if k in row},
                 source_graph="conceptual_graph", source_object_ids=[*(entities or []), *(connections or [])])  # fmt: skip
    )
    return row


def _pipe(connection: Connection) -> str:
    line, size = connection.properties.get("lineNumber"), connection.properties.get("nominalDiameterRepresentation")
    return ", ".join(p for p in (f"line {line}" if line else "", str(size) if size else "") if p)


# ================================================================== isolation boundary
def isolation_boundary(service: GraphService, entity_id: str) -> ToolResult:
    """The piping region around an item, up to the first valve on every branch.

    The search leaves the item along every pipe, in both directions, and passes fittings. It
    stops at a shut-off valve (a boundary valve), a check valve, a relief device, other
    equipment, an off-page connector and an open end. What is not a shut-off valve is
    reported as a connection the drawing does not let you isolate.
    """
    result = ToolResult(tool="isolation_boundary", status="success", input={"entity_id": entity_id})
    start = service._require_topology_entity(entity_id, result)
    if start is None:
        return result
    piping, entities = service.piping, service.index.entities
    if not piping.degree(start.id):
        result.status = "empty"
        result.message = f"{start.id} ({start.type}) has no piping connections, so it has no isolation boundary."
        return result
    operation, parameters = "isolation_boundary", {"entity_id": start.id}
    region, used = [start.id], []
    seen: set[str] = {start.id}
    queue: deque[tuple[str, str | None]] = deque([(start.id, None)])
    valves: list[tuple[str, Connection, str]] = []
    unisolated: list[tuple[str | None, Connection, str, str]] = []
    reliefs: list[tuple[str, Connection, str, bool]] = []
    while queue:
        node, first_side = queue.popleft()
        for connection in piping.at[node]:
            if connection.id in used:
                continue
            used.append(connection.id)
            leaving = connection.source == node  # drawn flow leaves ``node`` through this pipe
            side = first_side or ("downstream" if leaving else "upstream")
            if connection.open_end:
                unisolated.append((None, connection, side, "open_end"))
                continue
            other = connection.target if leaving else connection.source
            assert other is not None
            if other in seen:
                continue
            role = piping_role(entities[other])
            if role in ("isolation_valve", "check_valve"):
                seen.add(other)
                valves.append((other, connection, side))
            elif role == "relief_device":
                seen.add(other)
                reliefs.append((other, connection, side, leaving))
            elif role in ("off_page_connector", "equipment"):
                unisolated.append((other, connection, side, role))
            else:
                seen.add(other)
                region.append(other)
                queue.append((other, side))

    def emit(predicate: str, statement: str, other: str | None, connection: Connection | None, side: str | None, **extra: Any) -> None:
        add_derived(result, predicate, start.id, statement, operation=operation, parameters=parameters, object=other, entities=region, connections=used,
                    side=side, line=connection.properties.get("lineNumber") if connection else None,
                    diameter=connection.properties.get("nominalDiameterRepresentation") if connection else None, connection=connection.id if connection else None, **extra)  # fmt: skip

    here = label(service, start.id)
    shut_off = 0
    for valve, connection, side in valves:
        is_check = piping_role(entities[valve]) == "check_valve"
        beyond = piping.degree(valve) > 1
        text = f"{label(service, valve)} is the nearest valve on the {side} side of {here} ({_pipe(connection)})"
        if is_check:
            text += "; it is a check valve, not a shut-off valve"
        if not beyond:
            text += "; nothing is drawn beyond it"
        shut_off += not is_check
        emit("check_valve_on_boundary" if is_check else "isolation_boundary_valve", text, valve, connection, side, nothing_drawn_beyond=not beyond or None)
    for device, connection, side, relieves in reliefs:
        text = (
            f"{label(service, device)} is connected to the piping around {here} with no valve in between ({_pipe(connection)}); drawn flow runs from this piping into it"
            if relieves
            else f"{label(service, device)} discharges into the piping around {here} with no valve in between ({_pipe(connection)}); it does not relieve this region"
        )
        emit("relief_device_on_boundary", text, device, connection, side, relieves_region=relieves)
    for other, connection, side, kind in unisolated:
        if kind == "open_end":
            text = f"No valve on the {side} side of {here} before {_pipe(connection)} leaves the drawing: the other end of this pipe is not represented"
        elif kind == "off_page_connector":
            text = f"No valve between {here} and {label(service, other)} ({_pipe(connection)}): the piping leaves the drawing there"
        else:
            text = f"No valve between {here} and {label(service, other)} ({_pipe(connection)})"
        emit("unisolated_connection", text, other, connection, side, kind=kind)
    for item in region[1:]:
        if piping.degree(item) == 1:
            emit("closed_end_in_region", f"{label(service, item)} is an end of the drawn piping inside the region around {here}", item, None, None)

    bounded = not unisolated and not any(piping_role(entities[v]) == "check_valve" for v, _, _ in valves)
    relieving = [device for device, _, _, relieves in reliefs if relieves]
    names = ", ".join(label(service, v) for v, _, _ in valves) or "none"
    emit("fully_valve_bounded",
         f"Every connection of {here} ends at a shut-off valve, a relief device or a closed end ({shut_off} boundary valves: {names})" if bounded
         else f"{here} cannot be fully isolated with the valves on this drawing: {len(unisolated)} connection(s) have no shut-off valve",
         None, None, None)  # fmt: skip
    result.derived[-1]["value"] = bounded
    emit("relief_path_inside_boundary",
         f"With the boundary valves treated as closed, {here} still has a drawn path to {', '.join(label(service, d) for d in relieving)}" if relieving
         else f"With the boundary valves treated as closed, {here} has no drawn path to a relief device",
         None, None, None)  # fmt: skip
    result.derived[-1]["value"] = bool(relieving)
    result.entities.append(start.summary())
    result.meta.update({"region_entities": region, "boundary_valves": [v for v, _, _ in valves], "relief_devices": [d for d, *_ in reliefs],
                        "connections_without_valve": len(unisolated)})  # fmt: skip
    return result


# ================================================================== instrumentation chain
def trace_instrumentation(service: GraphService, entity_id: str) -> ToolResult:
    """All instrumentation links connected to an item, and the signal chains they form.

    Works from any member of a loop: the measured item, a sensor, a controller, an actuating
    function or the operated valve. Other loops are not entered through a shared pipe or valve.
    """
    result = ToolResult(tool="trace_instrumentation", status="success", input={"entity_id": entity_id})
    start = service._require_entity(entity_id, result)
    if start is None:
        return result
    entities = service.index.entities
    at: dict[str, list[Connection]] = {}
    for connection in service.index.connections.values():
        if connection.relationship == "instrumentation" and connection.source and connection.target:
            at.setdefault(connection.source, []).append(connection)
            at.setdefault(connection.target, []).append(connection)
    if start.id not in at:
        result.status = "empty"
        result.message = f"{start.id} ({start.type}) has no instrumentation links."
        result.entities.append(start.summary())
        return result
    members, links = [start.id], {}
    queue = deque([start.id])
    while queue:
        node = queue.popleft()
        if node != start.id and entities[node].category != "instrumentation":
            continue  # a measured item or an operated valve ends the loop
        for connection in at[node]:
            links[connection.id] = connection
            other = connection.target if connection.source == node else connection.source
            if other not in members:
                members.append(other)
                queue.append(other)

    def ordered(connection: Connection) -> tuple[str, str]:
        ends = (connection.source, connection.target)
        return (ends[1], ends[0]) if connection.connection_type in SIGNAL_ORDER_REVERSED else ends  # type: ignore[return-value]

    forward: dict[str, list[tuple[str, Connection]]] = {}
    has_input: set[str] = set()
    for connection in links.values():
        first, second = ordered(connection)
        forward.setdefault(first, []).append((second, connection))
        has_input.add(second)
    chains: list[tuple[list[str], list[Connection]]] = []

    def follow(node: str, path: list[str], used: list[Connection]) -> None:
        onward = [(n, c) for n, c in forward.get(node, []) if n not in path]
        if not onward:
            chains.append((path, used))
        for nxt, connection in onward:
            follow(nxt, [*path, nxt], [*used, connection])

    for origin in [m for m in members if m not in has_input]:
        follow(origin, [origin], [])

    for connection in sorted(links.values(), key=lambda c: (min((i for i, (p, _) in enumerate(chains) if c.source in p and c.target in p), default=0), c.id)):
        result.connections.append(service._connection_view(connection))
        result.evidence.append(service._connection_evidence(connection))
    facts: dict[str, dict[str, Any]] = {}
    for member in members:
        sources = service._property_sources(member, result)
        if sources is None:
            continue
        resolved, entries = sources
        if entities[member].category != "instrumentation":
            entries = [e for e in entries if e[0] in LINE_PROPERTIES]
        if entries:
            report = service._property_report(entries, None)
            result.properties[resolved] = report
            facts[member] = {item["property"]: item["value"] for item in report["found"]}
            for item in report["found"]:
                result.evidence.append(Evidence(kind="property", id=f"{item['source_object_id']}.{item['property']}", source_graph="plant_graph", source_object_ids=[item["source_object_id"]],
                                                fact={"object_id": item["source_object_id"], "property": item["property"], "value": item["value"], "scope": item["scope"]}))  # fmt: skip

    operation, parameters = "trace_instrumentation", {"entity_id": start.id}
    seen_rows: set[tuple[str, str, str]] = set()
    for path, used in chains:
        roles: dict[str, str] = {}
        for connection in used:
            if connection.connection_type == "sensing_location":
                roles[connection.target] = "measurement point"  # type: ignore[index]
            elif connection.connection_type == "operated_valve_reference":
                roles[connection.target] = "operated valve"  # type: ignore[index]
        fail = next((facts[m]["failAction"] for m in path if "failAction" in facts.get(m, {})), None)
        actuator = next((m for m in path if "failAction" in facts.get(m, {})), None)

        def describe(member: str) -> str:
            notes = [roles[member]] if member in roles else []
            if member == actuator:
                notes.append(f"encoded fail action: {fail}")
            if member in roles and facts.get(member, {}).get("lineNumber"):
                notes.append(f"line {facts[member]['lineNumber']}")
            return label(service, member) + (f" [{', '.join(notes)}]" if notes else "")

        ids = [c.id for c in used]
        add_derived(result, "signal_chain", path[0], "Signal chain: " + " -> ".join(describe(m) for m in path), operation=operation, parameters=parameters, object=path[-1],
                    entities=path, connections=ids, elements=path, fail_action=fail)  # fmt: skip
        measured = next((m for m in path if roles.get(m) == "measurement point"), None)
        valve = next((m for m in path if roles.get(m) == "operated valve"), None)
        for member in path:
            if entities[member].type != "ProcessInstrumentationFunction":
                continue
            if measured and ("measured_at", member, measured) not in seen_rows:
                seen_rows.add(("measured_at", member, measured))
                add_derived(result, "loop_measured_at", member, f"The measurement used by {label(service, member)} is taken at {label(service, measured)}", operation=operation, parameters=parameters,
                            object=measured, entities=path, connections=ids)  # fmt: skip
            if valve and ("acts_on", member, valve) not in seen_rows:
                seen_rows.add(("acts_on", member, valve))
                line = facts.get(valve, {}).get("lineNumber")
                text = f"{label(service, member)} acts on {label(service, valve)}" + (f" on line {line}" if line else "") + (f" through {label(service, actuator)}" if actuator else "")
                text += f"; encoded fail action of the actuator: {fail}" if fail else "; no fail action is encoded for the actuator"
                add_derived(result, "loop_acts_on", member, text, operation=operation, parameters=parameters, object=valve, entities=path, connections=ids,
                            fail_action=fail, via=actuator, line=line)  # fmt: skip
    result.entities.append(start.summary())
    result.meta.update({"members": members, "chains": len(chains)})
    return result


# ================================================================== one line and its branches
def _line_number(service: GraphService, text: str, known: dict[str, str]) -> str | None:
    for candidate in (text, *str(text).split()):
        if normalize_identifier(candidate) in known:
            return known[normalize_identifier(candidate)]
    entity = service.index.entities.get(str(text))
    if entity is None:
        resolution = service.resolver.resolve(str(text))
        entity = service.index.entities[resolution.entity_ids[0]] if resolution.status == "unique" else None
    number = (entity.identifiers.get("lineNumber") or (entity.piping_context or {}).get("lineNumber")) if entity else None
    return known.get(normalize_identifier(number)) if number else None


def trace_line(service: GraphService, line: str) -> ToolResult:
    """One piping line as runs between junctions, in drawn flow direction.

    A run goes from one junction, piece of equipment or line end to the next and lists what
    lies on it and its sizes. Places where the line meets another line are reported too.
    """
    result = ToolResult(tool="trace_line", status="success", input={"line": line})
    piping, entities = service.piping, service.index.entities
    pipes = [c for c in service.index.connections.values() if c.relationship == "piping" and c.properties.get("lineNumber")]
    known = {normalize_identifier(str(c.properties["lineNumber"])): str(c.properties["lineNumber"]) for c in pipes}
    number = _line_number(service, line, known)
    if number is None:
        result.status = "not_found"
        result.message = f"No piping line '{line}' exists in the P&ID graph."
        result.meta["lines"] = sorted(set(known.values()))
        return result
    on_line = [c for c in pipes if str(c.properties["lineNumber"]) == number]
    operation, parameters = "trace_line", {"line": number}
    outgoing: dict[str, list[Connection]] = {}
    has_incoming: set[str] = set()
    for connection in on_line:
        if connection.source:
            outgoing.setdefault(connection.source, []).append(connection)
        if connection.target:
            has_incoming.add(connection.target)

    def is_break(node: str) -> bool:
        if piping_role(entities[node]) in ("equipment", "off_page_connector") or piping.degree(node) != 2:
            return True
        return any(str(c.properties.get("lineNumber")) != number for c in piping.at[node])

    def end_kind(node: str | None) -> str:
        if node is None:
            return "not represented on this drawing"
        role = piping_role(entities[node])
        if role == "off_page_connector":
            return "the piping leaves the drawing here"
        if role == "equipment":
            return "equipment"
        return "end of the drawn piping" if piping.degree(node) == 1 else "junction"

    for connection in on_line:
        result.connections.append(service._connection_view(connection))
        result.evidence.append(service._connection_evidence(connection))
    starts = [c for c in on_line if c.source is None or is_break(c.source) or c.source not in has_incoming]
    for first in starts:
        components: list[str] = []
        sizes = [str(first.properties.get("nominalDiameterRepresentation") or "size not given")]
        used, current = [first.id], first
        while current.target is not None and not is_break(current.target) and len(outgoing.get(current.target, [])) == 1 and current.target not in components:
            components.append(current.target)
            current = outgoing[current.target][0]
            used.append(current.id)
            size = str(current.properties.get("nominalDiameterRepresentation") or "size not given")
            if size != sizes[-1]:
                sizes.append(size)
        text = f"Line {number}: from {label(service, first.source)} to {label(service, current.target)}"
        if components:
            text += " through " + ", ".join(label(service, c) for c in components)
        text += f"; {' then '.join(sizes)}; the run ends at: {end_kind(current.target)}"
        add_derived(result, "line_run", first.source or "open_end", text, operation=operation, parameters=parameters, object=current.target or "open_end",
                    entities=[i for i in (first.source, *components, current.target) if i], connections=used, line=number, components=components, diameters=sizes, ends_at=end_kind(current.target))  # fmt: skip
    nodes = {end for c in on_line for end in (c.source, c.target) if end}
    for node in sorted(nodes):
        for connection in piping.at[node]:
            other_line = str(connection.properties.get("lineNumber") or "")
            if other_line and other_line != number:
                other = connection.target if connection.source == node else connection.source
                way = "to" if connection.source == node else "from"
                add_derived(result, "line_meets_line", node, f"At {label(service, node)}, line {number} meets line {other_line} ({way} {label(service, other)}, {_pipe(connection)})",
                            operation=operation, parameters=parameters, value=other_line, entities=[i for i in (node, other) if i], connections=[connection.id], line=number, other_end=other)  # fmt: skip
    result.meta.update({"line": number, "runs": sum(r["predicate"] == "line_run" for r in result.derived), "items_on_line": sorted(nodes)})
    return result
