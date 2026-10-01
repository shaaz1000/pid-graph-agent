"""Turn an AgentResult into plain display data for the chat interface.

Nothing here calls the model or the graph, and nothing is inferred beyond what the result
already states: the UI only re-arranges the answer, trace, evidence and grounding outcome.
There is no confidence score because the agent does not compute one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pid_agent.agent.state import AgentResult

MAX_LINES = 12
PIPE_FIELDS = (("lineNumber", "line"), ("segmentNumber", "segment"), ("nominalDiameterRepresentation", ""), ("fluidCode", "fluid"))

# Nested fact fields worth showing in the evidence list; the raw tool result has the rest.
FACT_KEYS = ("lineNumber", "segmentNumber", "nominalDiameterRepresentation", "fluidCode", "pipingClassCode")

# (title, explanation) for each expected graph state. These are normal product states, not errors.
NOTICE_TEXT = {
    "not_found": "Entity not found",
    "ambiguous": "Several entities match",
    "missing_property": "Property not present in the graph",
    "no_path": "No represented path",
    "open_end": "Open graph boundary",
    "truncated": "Traversal stopped at its depth limit",
    "chamber_boundary": "Chamber boundary not crossed",
    "limit": "Agent budget reached",
    "withheld": "Draft answer withheld",
    "provider_failure": "Model provider failure",
    "config": "Configuration needed",
}

EXAMPLE_QUESTIONS = (
    ("Connectivity", "What is P4711 connected to, and through which pipes?"),
    ("Traversal", "Which valves are downstream of the heat exchanger H1007?"),
    ("Properties", "What is the nominal diameter of the line between P4711 and H1007?"),
    ("Inventory", "List every pump and what it feeds."),
    ("Instrumentation", "Which valve does HV4750.01 operate, and on which line is that valve installed?"),
    ("Missing data", "How much does heat exchanger H1007 weigh?"),
)


@dataclass
class Notice:
    kind: str
    title: str
    detail: str


@dataclass
class Candidate:
    id: str
    name: str
    type: str
    reason: str = ""


@dataclass
class StepView:
    number: int
    tool: str
    status: str
    executed: bool
    inputs: list[str]
    lines: list[str]
    raw: dict[str, Any]
    duration_ms: float = 0.0


@dataclass
class EvidenceView:
    kind: str
    id: str
    source_graph: str
    source_object_ids: list[str]
    fact: str


@dataclass
class FactView:
    id: str
    statement: str
    evidence_id: str
    source_graph: str
    source_object_ids: list[str]


@dataclass
class ClaimView:
    text: str
    facts: list[FactView]


@dataclass
class GroundingView:
    status: str
    ok: bool
    label: str
    detail: str
    rejected: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    # Deterministic validation state (grounded / limited / ambiguous / insufficient_evidence).
    level: str = "not_validated"
    claims: list[ClaimView] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


@dataclass
class AnswerView:
    question: str
    answer: str
    state: str  # answered | withheld | provider_failure | config_error
    steps: list[StepView] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    evidence: list[EvidenceView] = field(default_factory=list)
    grounding: GroundingView | None = None
    notices: list[Notice] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    usage: str = ""


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _inputs(arguments: dict[str, Any] | None) -> list[str]:
    return [f"{key} = {_text(value)}" for key, value in (arguments or {}).items() if value is not None]


def _pipe(row: dict[str, Any]) -> str:
    parts = [f"{label} {row[key]}".strip() for key, label in PIPE_FIELDS if row.get(key)]
    return " · ".join(parts)


def _connection_line(c: dict[str, Any]) -> str:
    source = c.get("from") or "(not on this drawing)"
    target = c.get("to") or "(not on this drawing)"
    line = f"{source} → {target}"
    if c.get("meaning"):
        return f"{line} · {c.get('type', 'link')}: {c['meaning']}"
    details = _pipe(c)
    if details:
        line += f" · {details}"
    if c.get("open_end"):
        line += " · open end"
    return line


def _entity_line(e: dict[str, Any]) -> str:
    name = e.get("name")
    line = e.get("id", "?") + (f" · {name}" if name and name != e.get("id") else "") + (f" · {e['type']}" if e.get("type") else "")
    if "distance" in e:
        line += f" · distance {e['distance']}"
        if e.get("through_equipment"):
            line += f" · through {', '.join(e['through_equipment'])}"
        if e.get("terminal"):
            line += " · end of drawn piping"
        if e.get("continues_beyond_max_depth"):
            line += " · continues beyond depth limit"
    elif e.get("match_reason"):
        line += f" · matched on {e['match_reason']}"
    context = _pipe(e.get("piping_context") or {})
    if context:
        line += f" · installed on {context}"
    return line


def _property_lines(properties: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for object_id, report in properties.items():
        if not isinstance(report, dict) or "found" not in report:
            lines.append(f"{object_id}: {_text(report)}")
            continue
        for item in report.get("found", []):
            owner = item.get("on", object_id)
            lines.append(f"{owner}.{item.get('property')} = {_text(item.get('value'))}")
        if report.get("missing"):
            lines.append(f"{object_id}: not present in the graph: {', '.join(report['missing'])}")
    return lines


def _boundary_line(b: dict[str, Any]) -> str:
    return f"{b.get('equipment', '?')}: entered through {b.get('entered_chamber', '?')}, did not cross to {b.get('blocked_chamber', '?')}"


def summarize_result(result: dict[str, Any]) -> list[str]:
    """Readable lines for one tool result (the compact view stored in the trace)."""
    lines: list[str] = []
    if result.get("message"):
        lines.append(str(result["message"]))
    if result.get("note"):
        lines.append(str(result["note"]))
    for path in result.get("paths") or []:
        lines.append(f"Route ({path.get('length', '?')} steps): " + " → ".join(path.get("entities", [])))
        lines.extend(_connection_line(step) for step in path.get("steps", []))
    lines.extend(_entity_line(e) for e in result.get("entities") or [])
    lines.extend(_connection_line(c) for c in result.get("connections") or [])
    lines.extend(_property_lines(result.get("properties") or {}))
    lines.extend("Chamber boundary · " + _boundary_line(b) for b in result.get("boundaries") or [])
    meta = result.get("meta") or {}
    if meta.get("endpoints"):
        lines.append("Ends of drawn piping: " + ", ".join(_text(e) for e in meta["endpoints"]))
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + [f"… {len(lines) - MAX_LINES} more lines (see raw result)"]
    return lines


def _step_notices(tool: str, status: str, result: dict[str, Any], arguments: dict[str, Any] | None) -> list[Notice]:
    found: list[tuple[str, str]] = []
    message = str(result.get("message", ""))
    if status == "not_found":
        suggestions = [f"{s.get('id', '?')} ({s['similar_to']})" if isinstance(s, dict) and s.get("similar_to") else _text(s) for s in (result.get("resolution") or {}).get("suggestions", [])]
        detail = message or f"{tool} found nothing for {_text(arguments)}."
        if suggestions:
            detail += f" Closest identifiers (suggestions only, not used): {', '.join(suggestions)}."
        found.append(("not_found", detail))
    if status == "ambiguous":
        found.append(("ambiguous", message or "The query matches more than one entity; the graph does not say which one is meant."))
    if tool == "find_path" and status == "empty":
        found.append(("no_path", message or "No piping path is represented between these entities in that direction."))
    for object_id, report in (result.get("properties") or {}).items():
        if isinstance(report, dict) and report.get("missing"):
            found.append(("missing_property", f"{object_id} has no {', '.join(report['missing'])} in the graph."))
    steps = [s for path in result.get("paths") or [] for s in path.get("steps", [])]
    for c in [*(result.get("connections") or []), *steps]:
        if c.get("open_end"):
            known = c.get("to") if c["open_end"] == "source" else c.get("from")
            end = "source" if c["open_end"] == "source" else "destination"
            pipe = _pipe(c)
            found.append(("open_end", f"A pipe at {known}" + (f" ({pipe})" if pipe else "") + f" has no {end} on this drawing. The graph does not say where it leads."))
    meta = result.get("meta") or {}
    if meta.get("truncated_by_max_depth"):
        beyond = ", ".join(_text(e) for e in meta.get("unexplored_beyond_max_depth", []))
        found.append(("truncated", f"The search stopped at depth {meta.get('max_depth', '?')}; piping continues beyond" + (f": {beyond}." if beyond else ".")))
    for b in result.get("boundaries") or []:
        found.append(("chamber_boundary", _boundary_line(b) + " (a separate side of the equipment)."))
    return [Notice(kind, NOTICE_TEXT[kind], detail) for kind, detail in found]


def _candidates(result: dict[str, Any]) -> list[Candidate]:
    return [
        Candidate(id=e.get("id", "?"), name=str(e.get("name", "")), type=str(e.get("type", "")), reason=str(e.get("match_reason", "")))
        for e in result.get("entities") or []
    ]


def _fact(fact: Any) -> str:
    if not isinstance(fact, dict):
        return _text(fact)
    parts = []
    for key, value in fact.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):  # nested property blocks: keep them short and readable
            value = ", ".join(f"{k}={_text(v)}" for k, v in value.items() if k in FACT_KEYS)
            if not value:
                continue
        parts.append(f"{key}: {_text(value)}")
    return " · ".join(parts)


def _fact_view(fact: dict[str, Any]) -> FactView:
    qualifiers = fact.get("qualifiers") or {}
    parts = [str(fact.get("subject", "?")), str(fact.get("predicate", "?"))]
    if qualifiers.get("property"):
        parts.append(str(qualifiers["property"]))
    for name in ("object", "value"):
        if fact.get(name) not in (None, ""):
            parts.append(_text(fact[name]))
    shown = {k: v for k, v in qualifiers.items() if k in (*FACT_KEYS, "direction", "distance", "connection", "missing_end", "entered_chamber", "blocked_chamber", "candidates")}
    statement = " ".join(parts) + (" (" + ", ".join(f"{k}: {_text(v)}" for k, v in shown.items()) + ")" if shown else "")
    return FactView(fact.get("id", "?"), statement, fact.get("evidence_id", ""), fact.get("source_graph", ""), list(fact.get("source_object_ids") or []))


def _grounding(data: dict[str, Any]) -> GroundingView:
    status = data.get("grounding_status", "not_validated")
    level = data.get("grounding_level") or "not_validated"
    checked = data.get("claims_checked", 0)
    unsupported = [f"{c.get('claim', '?')} ({c.get('reason', 'not in the tool results')})" for c in data.get("unsupported_claims") or []]
    rejected = [", ".join(str(c.get("claim", "?")) for c in d.get("unsupported_claims", [])) for d in data.get("rejected_drafts") or []]
    claims = [ClaimView(c.get("text", ""), [_fact_view(f) for f in c.get("facts") or []]) for c in data.get("claims") or []]
    gaps = [f"{g.get('claim', '?')}: {g.get('reason', '')}" for g in data.get("grounding_gaps") or []]
    rewrite = " A first draft was rejected and rewritten once." if status == "regenerated" else ""
    extra = {"rejected": rejected, "unsupported": unsupported, "claims": claims, "gaps": gaps}
    if status == "fallback" and not data.get("failure_category"):
        return GroundingView(status, False, "Insufficient evidence: draft withheld", "The answer above is assembled from tool results, not model text.", level="insufficient_evidence", **extra)
    if status not in ("grounded", "regenerated"):
        return GroundingView(status, False, "Not validated", "No model answer was produced, so there was nothing to check.", level="not_validated", **extra)
    if level == "not_validated":
        # A result saved before claim-level grounding existed: only the token-level check ran.
        return GroundingView(status, True, "Token-level check passed", f"This run predates structured claims. {checked} identifiers and values were found in the tool results.{rewrite}", level="limited", **extra)
    if level == "grounded":
        return GroundingView(status, True, "Grounded: every claim matched graph evidence", f"{len(claims)} statements, each supported by the graph facts it cites.{rewrite}", level=level, **extra)
    if level == "ambiguous":
        return GroundingView(status, True, "Ambiguous: the graph returned several matches", f"{len(claims)} statements validated; no single entity was selected.{rewrite}", level=level, **extra)
    return GroundingView(status, False, "Partially grounded (limited)", f"{len(claims)} statements validated; {len(gaps)} item(s) were supported only by evidence the answer did not cite.{rewrite}", level="limited", **extra)


def build_view(result: AgentResult | dict[str, Any]) -> AnswerView:
    """The display model for one agent run. Missing optional fields are tolerated."""
    data = result.to_dict() if isinstance(result, AgentResult) else dict(result)
    steps: list[StepView] = []
    notices: list[Notice] = []
    candidates: list[Candidate] = []
    warnings: list[str] = []
    for raw_step in data.get("trace") or []:
        step = raw_step if isinstance(raw_step, dict) else raw_step.model_dump()
        payload = step.get("result") or {}
        status = step.get("status", "unknown")
        steps.append(
            StepView(
                number=step.get("step", len(steps) + 1),
                tool=step.get("tool", "?"),
                status=status,
                executed=step.get("executed", True),
                inputs=_inputs(step.get("input")),
                lines=summarize_result(payload),
                raw=payload,
                duration_ms=step.get("duration_ms", 0.0),
            )
        )
        notices.extend(_step_notices(step.get("tool", "?"), status, payload, step.get("input")))
        if status == "ambiguous":
            candidates = _candidates(payload)
        warnings.extend(str(w) for w in payload.get("warnings") or [])

    state = "answered"
    if data.get("failure_category"):
        state = "provider_failure"
        notices.insert(0, Notice("provider_failure", NOTICE_TEXT["provider_failure"], f"{data['failure_category']}: the model could not be reached. This says nothing about the P&ID."))
    elif data.get("grounding_status") == "fallback":
        state = "withheld"
        notices.insert(0, Notice("withheld", NOTICE_TEXT["withheld"], "The model's draft was not supported by the graph evidence, so the tool results are shown instead."))
    if data.get("limit_reached"):
        notices.append(Notice("limit", NOTICE_TEXT["limit"], str(data["limit_reached"])))

    usage = data.get("usage") or {}
    executed = [s for s in steps if s.executed]
    return AnswerView(
        question=data.get("question", ""),
        answer=data.get("answer", ""),
        state=state,
        steps=steps,
        summary=[f"{s.number}. {s.tool}({', '.join(s.inputs)}) → {s.status}" for s in steps],
        evidence=[
            EvidenceView(e.get("kind", "?"), e.get("id", "?"), e.get("source_graph", "?"), list(e.get("source_object_ids") or []), _fact(e.get("fact")))
            for e in data.get("evidence") or []
        ],
        grounding=_grounding(data),
        notices=_dedupe(notices),
        candidates=candidates,
        warnings=list(dict.fromkeys(warnings)),
        usage=f"{usage.get('llm_calls', 0)} model calls · {len(executed)} tool calls · {usage.get('total_tokens', 0)} tokens · {data.get('duration_ms', 0.0) / 1000:.1f} s",
    )


def error_view(question: str, message: str) -> AnswerView:
    """A configuration problem (for example a missing API key): no agent run happened."""
    return AnswerView(question=question, answer="The agent could not be started.", state="config_error", notices=[Notice("config", NOTICE_TEXT["config"], message)])


def _dedupe(notices: list[Notice]) -> list[Notice]:
    seen: set[tuple[str, str]] = set()
    out = []
    for notice in notices:
        if (notice.kind, notice.detail) not in seen:
            seen.add((notice.kind, notice.detail))
            out.append(notice)
    return out


def graph_facts(service: Any, loaded: Any) -> dict[str, Any]:
    """Counts shown in the sidebar, read from the loaded graphs and the normalized index."""
    index = service.index
    entities = list(index.entities.values()) if isinstance(index.entities, dict) else list(index.entities)
    connections = list(index.connections.values()) if isinstance(index.connections, dict) else list(index.connections)
    categories: dict[str, int] = {}
    for entity in entities:
        categories[entity.category] = categories.get(entity.category, 0) + 1
    kinds: dict[str, int] = {}
    for connection in connections:
        kinds[connection.connection_type] = kinds.get(connection.connection_type, 0) + 1
    return {
        "file": loaded.source_file.name,
        "plant": (loaded.plant_graph.number_of_nodes(), loaded.plant_graph.number_of_edges()),
        "conceptual": (loaded.conceptual_graph.number_of_nodes(), loaded.conceptual_graph.number_of_edges()),
        "entities": categories,
        "connections": kinds,
    }
