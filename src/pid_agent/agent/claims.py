"""Claim-level grounding.

The answer's plant facts are stated as structured claims (subject, predicate, object/value,
qualifiers). Each claim is supported only if a *typed fact* derived from the tool results
entails it: the right subject, the right relation or property, the right value and unit.
A string appearing somewhere in the evidence is not enough.

    tool results (structured)  ->  Fact index   (build_facts)
    answer text + claims block ->  claims        (split_answer)
    claim  x  facts            ->  supported / rejected, with the supporting facts (validate_claim)

Facts are derived only from graph data in the tool results. Tool inputs, messages and warnings
never become facts, with one exception that is about the input by nature: "this query was not
found / was ambiguous". No model is involved in validation.

The token-level check in ``grounding.py`` remains as a second, purely restrictive layer: it
can reject text, never accept a claim.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from pid_agent.agent.grounding import (
    DISCLAIMER,
    SENTENCE_SPLIT,
    TYPOGRAPHY,
    EvidenceCorpus,
    _attribution_problem,
    _role_problems,
    extract_claims,
)

INSTRUMENT_PREDICATES = {
    "operated_valve_reference": "operates",
    "signal_line": "sends_signal_to",
    "sensing_location": "senses_at",
    "measuring_line": "measurement_input_to",
}
PREDICATES = (
    "is_a", "identified_as", "has_property", "lacks_property", "connected_to", *INSTRUMENT_PREDICATES.values(),
    "reachable", "path", "no_path", "open_end", "terminal", "continues_beyond_depth", "chamber_boundary",
    "not_found", "ambiguous",
)  # fmt: skip
ROLE_PREFIX = re.compile(r"^(?:line|segment|connection|pipe|entity|equipment|valve|nozzle|chamber)\s+(?:number\s+|no\.?\s*)?", re.IGNORECASE)
WITH_NAME = re.compile(r"^(.*?)\s*[\(\[](.*)[\)\]]$")
DN = re.compile(r"^dn\s?(\d+(?:\.\d+)?)\s*(.*)$", re.IGNORECASE)
QUANTITY = re.compile(r"^(-?\d+(?:\.\d+)?)\s*(.*)$")
CLAIMS_BLOCK = re.compile(r"```[ \t]*(?:claims|json)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
CLAIMS_HEADING = re.compile(r"(?:\n|^)[#*\s]*(?:structured\s+)?claims[*\s]*:?[*\s]*$", re.IGNORECASE)
# Assertions about present operating state. A P&ID holds topology and design data, not state.
LIVE_STATE = re.compile(
    r"\b(?:is|are)\s+(?:currently|now|presently)\b|\b(?:currently|right now|at the moment|presently)\s+(?:open|closed|shut|running|flowing|operating)\b"
    r"|\b(?:is|are)\s+(?:open|closed|shut|running|flowing)(?![\w-])",
    re.IGNORECASE,
)
PROMPT_LEAK_LENGTH = 80


def key(text: Any) -> str:
    """Identifier comparison form: case, spacing and wrapping punctuation ignored."""
    return re.sub(r"\s+", "", str(text).translate(TYPOGRAPHY).casefold()).strip(".,;:`*'\"")


def name_tokens(name: Any) -> tuple[str, ...]:
    """'nominalDiameterRepresentation', 'nominal_diameter', 'Nominal diameter' -> word tuples."""
    return tuple(t.lower() for t in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", str(name)))


def parse_value(text: Any) -> tuple:
    """A typed value. Units are part of the value; a DN designation is not a length.

    No unit conversion is performed: 80 mm, DN 80, 80 bar and 80 are four different values.
    Only spelling is normalised (60 = 60.0, m² = m2, spacing, typographic minus).
    """
    raw = str(text).translate(TYPOGRAPHY).strip()
    match = DN.match(raw)
    if match:
        return ("dn", float(match.group(1)), key(match.group(2)))
    match = QUANTITY.match(raw)
    if match:
        unit = key(match.group(2)).replace("³", "3").replace("²", "2")
        return ("quantity", float(match.group(1)), unit) if unit else ("number", float(match.group(1)))
    return ("text", key(raw))


def values_match(claimed: Any, actual: Any) -> bool:
    if isinstance(actual, (list, tuple, set)):
        return any(values_match(claimed, item) for item in actual)
    return parse_value(claimed) == parse_value(actual)


# Suffix words of DEXPI attribute names that do not change which property is meant.
GENERIC_NAME_WORDS = {"representation", "numerical", "value", "standard", "number", "code", "id", "name"}


def names_match(claimed: Any, actual: Any) -> bool:
    """Same property name, allowing only generic suffix words to be left out.

    "nominal diameter" matches nominalDiameterRepresentation and "line" matches lineNumber;
    "tagName" does not match tagNamePrefix and "design pressure" does not match
    upperLimitDesignPressure.
    """
    wanted, have = name_tokens(claimed), name_tokens(actual)
    if not wanted:
        return False
    return wanted == have or (set(wanted) <= set(have) and set(have) - set(wanted) <= GENERIC_NAME_WORDS)


@dataclass
class Fact:
    """One typed graph observation, traceable to the tool result and DEXPI objects it came from."""

    id: str
    predicate: str
    subject: str
    object: str | None = None
    value: Any = None
    qualifiers: dict[str, Any] = field(default_factory=dict)
    tool: str = ""
    evidence_id: str = ""
    source_graph: str = ""
    source_object_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, "", [], {})}


class FactIndex:
    def __init__(self) -> None:
        self.facts: list[Fact] = []
        self.aliases: dict[str, set[str]] = {}       # entity identifier -> entity ids
        self.objects: set[str] = set()                # ids of connections and sub-objects
        self.line_aliases: dict[str, set[str]] = {}   # line number -> connection / line ids
        self._canonical: dict[str, str] = {}

    def add(self, predicate: str, subject: str, *, object: str | None = None, value: Any = None, qualifiers: dict[str, Any] | None = None,
            tool: str = "", evidence: dict[str, Any] | None = None, source_graph: str = "", evidence_id: str = "") -> Fact:  # fmt: skip
        fact = Fact(
            id=f"F{len(self.facts) + 1}", predicate=predicate, subject=subject, object=object, value=value,
            qualifiers={k: v for k, v in (qualifiers or {}).items() if v not in (None, "", [], {})}, tool=tool,
            evidence_id=(evidence or {}).get("id", evidence_id), source_graph=(evidence or {}).get("source_graph", source_graph),
            source_object_ids=list((evidence or {}).get("source_object_ids", [])),
        )  # fmt: skip
        self.facts.append(fact)
        return fact

    def alias(self, text: Any, entity_id: str) -> None:
        if text not in (None, ""):
            self.aliases.setdefault(key(text), set()).add(entity_id)
            self._canonical[key(entity_id)] = entity_id

    def known_object(self, object_id: str) -> None:
        self.objects.add(object_id)
        self._canonical[key(object_id)] = object_id

    def resolve(self, text: Any) -> tuple[list[str], str]:
        """Ids a claim's subject/object refers to, and how: 'entity', 'object', 'line', 'ambiguous' or 'unknown'."""
        raw = str(text or "").strip().strip("`*")
        forms = [raw]
        match = WITH_NAME.match(raw)
        if match:
            forms += [match.group(1), match.group(2)]
        forms += [ROLE_PREFIX.sub("", form) for form in list(forms)]
        for form in forms:
            k = key(form)
            if k in self.aliases:
                ids = sorted(self.aliases[k])
                return (ids, "entity") if len(ids) == 1 else (ids, "ambiguous")
            if k in self._canonical and self._canonical[k] in self.objects:
                return [self._canonical[k]], "object"
        for form in forms:
            if key(form) in self.line_aliases:
                return sorted(self.line_aliases[key(form)]), "line"
        return [], "unknown"

    def names_of(self, entity_id: str) -> set[str]:
        return {str(f.value) for f in self.facts if f.predicate == "identified_as" and f.subject == entity_id}

    def where(self, predicate: str) -> list[Fact]:
        return [f for f in self.facts if f.predicate == predicate]


# --------------------------------------------------------------------------- facts from results
def _evidence_map(result: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(e["kind"], e["id"]): e for e in result.get("evidence", [])}


def _entity_facts(index: FactIndex, entity: dict[str, Any], tool: str, evidence: dict) -> None:
    eid = entity.get("id")
    if not eid or "type" not in entity:
        return
    ev = evidence.get(("entity", eid)) or {"id": eid, "source_graph": "plant_graph", "source_object_ids": [eid]}
    seen = {(f.predicate, key(f.value)) for f in index.facts if f.subject == eid and f.predicate in ("is_a", "identified_as")}

    def once(predicate: str, value: Any, **qualifiers: Any) -> None:
        if value not in (None, "") and (predicate, key(value)) not in seen:
            seen.add((predicate, key(value)))
            index.add(predicate, eid, value=value, qualifiers=qualifiers, tool=tool, evidence=ev)

    for label, value in (("id", eid), ("name", entity.get("name")), ("tag", entity.get("tag")), *(entity.get("identifiers") or {}).items()):
        once("identified_as", value, field=label)
        index.alias(value, eid)
    for type_name in (entity["type"], *entity.get("type_hierarchy", []), entity.get("category")):
        once("is_a", type_name)
    for scope in ("properties", "piping_context"):
        for name, value in (entity.get(scope) or {}).items():
            index.add("has_property", eid, value=value, qualifiers={"property": name, "scope": scope}, tool=tool, evidence=ev)
    for child in entity.get("children") or []:
        index.known_object(child["id"])
        child_ev = {"id": child["id"], "source_graph": "plant_graph", "source_object_ids": [child["id"]]}
        index.add("is_a", child["id"], value=child["type"], qualifiers={"part_of": eid}, tool=tool, evidence=child_ev)
        for name, value in (child.get("properties") or {}).items():
            index.add("has_property", child["id"], value=value, qualifiers={"property": name, "owner": eid}, tool=tool, evidence=child_ev)


def _nozzle(nozzle: dict[str, Any] | None) -> dict[str, Any]:
    if not nozzle:
        return {}
    label = nozzle.get("sub_tag") or nozzle.get("id")
    chamber = nozzle.get("chamber_id")
    return {"nozzle": [label, nozzle.get("id"), f"{label} [{chamber}]", f"{label} ({chamber})"] if chamber else [label, nozzle.get("id")], "chamber": chamber}


def _connection_facts(index: FactIndex, connection: dict[str, Any], tool: str, evidence: dict) -> None:
    cid = connection["id"]
    if any(f.qualifiers.get("connection") == cid for f in index.facts):
        return
    kind = "open_end" if connection.get("open_end") else "connection"
    provenance = connection.get("provenance", {})
    ev = evidence.get((kind, cid)) or {"id": cid, "source_graph": provenance.get("derived_from", "conceptual_graph"), "source_object_ids": provenance.get("source_object_ids", [cid])}
    index.known_object(cid)
    properties = connection.get("properties") or {}
    source, target = connection.get("source"), connection.get("target")
    for ref in (source, target):
        if ref:
            _entity_facts(index, ref, tool, evidence)
    for name, value in properties.items():
        index.add("has_property", cid, value=value, qualifiers={"property": name, "scope": "connection"}, tool=tool, evidence=ev)
    if properties.get("lineNumber"):
        index.line_aliases.setdefault(key(properties["lineNumber"]), set()).add(cid)
    start, end = _nozzle(connection.get("source_nozzle")), _nozzle(connection.get("target_nozzle"))
    qualifiers = {
        "connection": cid, "connection_type": connection["connection_type"], **properties,
        "from_nozzle": start.get("nozzle"), "to_nozzle": end.get("nozzle"), "from_chamber": start.get("chamber"), "to_chamber": end.get("chamber"),
    }  # fmt: skip
    if connection.get("open_end"):
        known = target if connection["open_end"] == "source" else source
        qualifiers["missing_end"] = "source" if connection["open_end"] == "source" else "destination"
        index.add("open_end", known["id"], qualifiers=qualifiers, tool=tool, evidence=ev)
    elif connection["relationship"] == "piping":
        index.add("flows_to", source["id"], object=target["id"], qualifiers=qualifiers, tool=tool, evidence=ev)
    else:
        index.add(INSTRUMENT_PREDICATES[connection["connection_type"]], source["id"], object=target["id"], qualifiers=qualifiers, tool=tool, evidence=ev)


def build_facts(observations: list[dict[str, Any]]) -> FactIndex:
    """Typed facts from the full tool results. Inputs, messages and warnings are not read."""
    index = FactIndex()
    for number, result in enumerate(observations, start=1):
        tool, evidence = result.get("tool", ""), _evidence_map(result)
        origin = f"{tool}#{number}"
        direction = (result.get("input") or {}).get("direction") or "downstream"
        for entity in result.get("entities") or []:
            _entity_facts(index, entity, tool, evidence)
        for (kind, entity_id), item in evidence.items():
            # An identifier the tool resolved while executing (recorded as entity evidence).
            fact = item["fact"]
            if kind == "entity" and isinstance(fact.get("type"), str) and fact.get("name") and entity_id not in index.objects:
                _entity_facts(index, {"id": entity_id, "type": fact["type"], "name": fact["name"], "tag": fact.get("tagName")}, tool, evidence)
        for connection in result.get("connections") or []:
            _connection_facts(index, connection, tool, evidence)

        for path in result.get("paths") or []:
            ids = [e["id"] for e in path["entities"]]
            for ref in path["entities"]:
                _entity_facts(index, ref, tool, evidence)
            for step in path.get("steps", []):
                _connection_facts(index, step["connection"], tool, evidence)
            ev = evidence.get(("path", f"{ids[0]}->{ids[-1]}"))
            index.add("path", ids[0], object=ids[-1], qualifiers={"entities": ids, "direction": path.get("direction"), "length": path.get("length")}, tool=tool, evidence=ev, source_graph="conceptual_graph", evidence_id=origin)

        if tool == "traverse":
            for entity in result.get("entities") or []:
                route = entity.get("path_entities") or []
                if not route:
                    continue
                ev = evidence.get(("path", f"{route[0]}->{entity['id']}"))
                index.add("reaches", route[0], object=entity["id"], tool=tool, evidence=ev, source_graph="conceptual_graph", evidence_id=origin,
                          qualifiers={"direction": direction, "distance": entity.get("distance"), "entities": route, "through_equipment": entity.get("through_equipment")})  # fmt: skip
                for flag, predicate in (("terminal", "terminal"), ("continues_beyond_max_depth", "continues_beyond_depth")):
                    if entity.get(flag):
                        index.add(predicate, entity["id"], qualifiers={"direction": direction}, tool=tool, source_graph="conceptual_graph", evidence_id=origin)
            meta = result.get("meta") or {}
            for field_name, predicate in (("endpoints", "terminal"), ("unexplored_beyond_max_depth", "continues_beyond_depth")):
                for entity_id in meta.get(field_name) or []:
                    index.known_object(entity_id)
                    index.add(predicate, entity_id, qualifiers={"direction": direction}, tool=tool, source_graph="conceptual_graph", evidence_id=f"{origin}:meta.{field_name}")

        missing = (result.get("meta") or {}).get("no_path")
        if missing:
            for entity_id in (missing["source"], missing["target"]):
                index.known_object(entity_id)
            index.add("no_path", missing["source"], object=missing["target"], qualifiers={"direction": missing["direction"]}, tool=tool, source_graph="conceptual_graph", evidence_id=origin)

        for boundary in result.get("boundaries") or []:
            ev = next((e for (kind, _), e in evidence.items() if kind == "boundary" and e["fact"].get("blocked_connection") == boundary.get("blocked_connection")), None)
            index.add("chamber_boundary", boundary["equipment"], tool=tool, evidence=ev, source_graph="plant_graph", evidence_id=origin,
                      qualifiers={k: boundary.get(k) for k in ("entered_chamber", "blocked_chamber", "blocked_connection", "direction")})  # fmt: skip

        for object_id, report in (result.get("properties") or {}).items():
            if not isinstance(report, dict) or "found" not in report:
                continue
            index.known_object(object_id)
            for item in report["found"]:
                owner = item["source_object_id"]
                index.known_object(owner)
                ev = evidence.get(("property", f"{owner}.{item['property']}")) or {"id": f"{owner}.{item['property']}", "source_graph": "plant_graph", "source_object_ids": [owner]}
                index.add("has_property", owner, value=item["value"], qualifiers={"property": item["property"], "owner": object_id, "scope": item.get("scope")}, tool=tool, evidence=ev)
            for name in report.get("missing") or []:
                index.add("lacks_property", object_id, qualifiers={"property": name}, tool=tool, source_graph="plant_graph", evidence_id=f"{origin}:missing")

        if tool == "find_entities" and result.get("status") in ("not_found", "ambiguous"):
            query = (result.get("input") or {}).get("query")
            if result["status"] == "not_found":
                index.add("not_found", "query", value=query, tool=tool, source_graph="entity_index", evidence_id=f"{origin}:resolution")
            else:
                candidates = [e["id"] for e in result.get("entities") or []]
                index.add("ambiguous", "query", value=query, qualifiers={"candidates": candidates}, tool=tool, source_graph="entity_index", evidence_id=f"{origin}:resolution")
    return index


# --------------------------------------------------------------------------- claims
def split_answer(draft: str) -> tuple[str, list[Any] | None]:
    """The prose and the structured claims of a draft. ``None`` when there is no usable claims block."""
    text = draft or ""
    for match in reversed(list(CLAIMS_BLOCK.finditer(text))):
        try:
            data = json.loads(match.group(1))
        except ValueError:
            continue
        if isinstance(data, dict):
            data = data.get("claims")
        if isinstance(data, list):
            prose = (text[: match.start()] + text[match.end():]).strip()
            return CLAIMS_HEADING.sub("", prose).strip(), data
    return text.strip(), None


def render_claim(claim: Any) -> str:
    if not isinstance(claim, dict):
        return str(claim)[:120]
    parts = [str(claim.get("subject", ""))] if claim.get("subject") else []
    if claim.get("property"):
        parts.append(str(claim["property"]))
    for name in ("object", "value"):
        if claim.get(name) not in (None, ""):
            parts.append(("-> " if name == "object" else "= ") + str(claim[name]))
    qualifiers = claim.get("qualifiers") if isinstance(claim.get("qualifiers"), dict) else {}
    parts += [f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v}" for k, v in qualifiers.items()]
    return f"{claim.get('predicate', '?')}({', '.join(parts)})"


def _qualifiers_hold(wanted: dict[str, Any], fact: Fact, skip: tuple[str, ...] = ()) -> str | None:
    """None when every claimed qualifier is carried by the fact, else what is not."""
    for name, value in wanted.items():
        if name in skip:
            continue
        carried = [v for k, v in fact.qualifiers.items() if names_match(name, k)]
        if not carried:
            return f"the evidence for this relation has no '{name}'"
        if not any(values_match(value, v) for v in carried):
            return f"'{name}' is {carried[0] if len(carried) == 1 else carried} in the evidence, not {value}"
    return None


def _subsequence(wanted: list[str], route: list[str]) -> bool:
    position = 0
    for item in route:
        if position < len(wanted) and item == wanted[position]:
            position += 1
    return position == len(wanted)


def validate_claim(claim: Any, index: FactIndex) -> tuple[bool, str, list[Fact]]:
    """(supported, reason, supporting facts). Anything not positively entailed is unsupported."""
    if not isinstance(claim, dict) or not isinstance(claim.get("predicate"), str):
        return False, "not a claim object with a predicate", []
    predicate = claim["predicate"].strip().lower()
    qualifiers = claim.get("qualifiers") or {}
    if predicate not in PREDICATES:
        return False, f"'{predicate}' is not a relation the graph tools provide", []
    if not isinstance(qualifiers, dict):
        return False, "qualifiers must be an object", []

    if predicate in ("not_found", "ambiguous"):
        wanted = claim.get("value") or claim.get("subject")
        facts = [f for f in index.where(predicate) if key(f.value) == key(wanted)]
        if not facts:
            return False, f"no lookup of '{wanted}' returned {predicate.replace('_', ' ')}", []
        for candidate in qualifiers.get("candidates") or []:
            ids, _ = index.resolve(candidate)
            if not set(ids) & set(facts[0].qualifiers.get("candidates", [])):
                return False, f"'{candidate}' is not one of the candidates returned", []
        return True, "", facts[:1]

    subjects, how = index.resolve(claim.get("subject"))
    if how == "ambiguous":
        return False, f"'{claim.get('subject')}' matches several entities ({', '.join(subjects)}); none was selected by the graph", []
    if how == "unknown":
        return False, f"subject '{claim.get('subject')}' was not identified by any tool result", []

    if predicate in ("is_a", "identified_as"):
        if predicate == "is_a":
            facts = [f for f in index.where("is_a") if f.subject in subjects and name_tokens(f.value) == name_tokens(claim.get("value"))]
        else:
            facts = [f for f in index.where("identified_as") if f.subject in subjects and key(f.value) == key(claim.get("value"))]
        return (True, "", facts[:1]) if facts else (False, f"the graph does not give {subjects[0]} the {'type' if predicate == 'is_a' else 'identifier'} '{claim.get('value')}'", [])

    if predicate in ("has_property", "lacks_property"):
        name = claim.get("property")
        if not name:
            return False, "no property named", []
        about = [f for f in index.where(predicate) if f.subject in subjects or f.qualifiers.get("owner") in subjects]
        if predicate == "lacks_property":
            facts = [f for f in about if name_tokens(f.qualifiers["property"]) == name_tokens(name)]
            return (True, "", facts[:1]) if facts else (False, f"no tool result reports '{name}' as missing for {subjects[0]}", [])
        named = [f for f in about if names_match(name, f.qualifiers["property"])]
        if not named:
            return False, f"no property '{name}' was returned for {claim.get('subject')}", []
        facts = [f for f in named if values_match(claim.get("value"), f.value)]
        if not facts:
            return False, f"'{name}' of {claim.get('subject')} is {', '.join(sorted({str(f.value) for f in named}))} in the graph, not {claim.get('value')}", named[:1]
        return True, "", facts[:1]

    if predicate in ("open_end", "terminal", "continues_beyond_depth", "chamber_boundary"):
        problem = "no such fact"
        for fact in (f for f in index.where(predicate) if f.subject in subjects):
            problem = _qualifiers_hold(qualifiers, fact)
            if problem is None:
                return True, "", [fact]
        return False, f"the tool results do not establish {predicate.replace('_', ' ')} for {subjects[0]}: {problem}", []

    # ---- relations between two entities
    objects, how = index.resolve(claim.get("object"))
    if how in ("ambiguous", "unknown"):
        return False, f"object '{claim.get('object')}' was not identified uniquely by any tool result", []
    direction = str(qualifiers.get("direction") or "").lower()
    if direction not in ("", "downstream", "upstream", "any", "both"):
        return False, f"unknown direction '{direction}'", []

    if predicate == "connected_to":
        candidates = [(f, "downstream") for f in index.where("flows_to") if f.subject in subjects and f.object in objects]
        candidates += [(f, "upstream") for f in index.where("flows_to") if f.subject in objects and f.object in subjects]
        if not candidates:
            return False, f"no direct piping connection between {subjects[0]} and {objects[0]} is in the tool results", []
        problem = None
        for fact, actual in candidates:
            if direction in ("downstream", "upstream") and direction != actual:
                problem = f"{objects[0]} is {actual} of {subjects[0]}, not {direction}"
                continue
            problem = _qualifiers_hold(qualifiers, fact, skip=("direction",))
            if problem is None:
                return True, "", [fact]
        return False, problem or "not supported", [candidates[0][0]]

    if predicate in INSTRUMENT_PREDICATES.values():
        facts = [f for f in index.where(predicate) if f.subject in subjects and f.object in objects]
        if facts:
            return True, "", facts[:1]
        reverse = [f for f in index.where(predicate) if f.subject in objects and f.object in subjects]
        reason = "the link runs the other way" if reverse else f"no '{predicate}' link from {subjects[0]} to {objects[0]} is in the tool results"
        return False, reason, reverse[:1]

    if predicate == "no_path":
        facts = [f for f in index.where("no_path") if f.subject in subjects and f.object in objects and (not direction or f.qualifiers.get("direction") == direction)]
        return (True, "", facts[:1]) if facts else (False, "no path search between these entities came back empty", [])

    routes = [f for f in index.where("path") + index.where("reaches") if f.subject in subjects and f.object in objects]
    if predicate == "reachable":
        routes += [f for f in index.where("flows_to") if f.subject in subjects and f.object in objects and direction in ("", "downstream")]
        routes += [f for f in index.where("flows_to") if f.subject in objects and f.object in subjects and direction in ("", "upstream")]
    if not routes:
        return False, f"no traversal or path result reaches {objects[0]} from {subjects[0]}", []
    problem = None
    for fact in routes:
        actual = fact.qualifiers.get("direction", "downstream" if fact.subject in subjects else "upstream")
        if fact.predicate == "flows_to":
            actual = "downstream" if fact.subject in subjects else "upstream"
        if direction in ("downstream", "upstream") and actual not in (direction, "any", "both"):
            problem = f"the result reaches {objects[0]} going {actual}, not {direction}"
            continue
        wanted = qualifiers.get("entities")
        if wanted is not None:
            resolved = [index.resolve(item)[0] for item in wanted] if isinstance(wanted, list) else None
            if not resolved or any(len(ids) != 1 for ids in resolved) or not _subsequence([ids[0] for ids in resolved], fact.qualifiers.get("entities", [])):
                problem = "the listed entities are not on this route in that order"
                continue
        problem = _qualifiers_hold(qualifiers, fact, skip=("direction", "entities"))
        if problem is None:
            return True, "", [fact]
    return False, problem or "not supported", routes[:1]


# --------------------------------------------------------------------------- the whole answer
@dataclass
class ClaimReport:
    answer: str = ""
    has_claims: bool = False
    supported: list[dict[str, Any]] = field(default_factory=list)    # claim, facts
    rejected: list[dict[str, Any]] = field(default_factory=list)     # claim, reason
    problems: list[dict[str, Any]] = field(default_factory=list)     # must not reach the user
    gaps: list[dict[str, Any]] = field(default_factory=list)         # shown only as "limited"
    checked: int = 0
    anchored: bool = False  # the answer rests on at least one graph-derived statement

    @property
    def level(self) -> str:
        if self.problems or not self.anchored:
            return "insufficient_evidence"
        if self.gaps:
            return "limited"
        return "ambiguous" if any(c["claim"].get("predicate") == "ambiguous" for c in self.supported) else "grounded"


def _covered_strings(report: ClaimReport, index: FactIndex) -> list[str]:
    """What the supported claims themselves state, plus other names of the entities they name."""
    out: list[str] = []
    for item in report.supported:
        claim = item["claim"]
        qualifiers = claim.get("qualifiers") or {}
        values = [claim.get(k) for k in ("subject", "object", "value", "property")] + list(qualifiers.keys())
        for value in qualifiers.values():
            values += value if isinstance(value, list) else [value]
        out += [str(v) for v in values if v not in (None, "")]
        for name in ("subject", "object"):
            for entity_id in index.resolve(claim.get(name))[0] if claim.get(name) else []:
                out += [entity_id, *index.names_of(entity_id)]
        out += [item for v in qualifiers.get("entities") or [] for entity_id in index.resolve(v)[0] for item in (entity_id, *index.names_of(entity_id))]
    return [re.sub(r"[\[\]]", " ", text) for text in out]


def _problem(claim: str, kind: str, reason: str, sentence: str = "") -> dict[str, Any]:
    return {"claim": claim, "kind": kind, "reason": reason, **({"sentence": sentence} if sentence else {})}


def check_answer(draft: str, question: str, observations: list[dict[str, Any]], protected_text: str = "") -> ClaimReport:
    """Validate one drafted answer. Deterministic; no model call."""
    prose, claims = split_answer(draft)
    index = build_facts(observations)
    report = ClaimReport(answer=prose, has_claims=claims is not None)

    for claim in claims or []:
        report.checked += 1
        ok, reason, facts = validate_claim(claim, index)
        if ok:
            report.supported.append({"claim": claim, "text": render_claim(claim), "facts": [f.to_dict() for f in facts]})
        else:
            report.rejected.append({"claim": claim, "text": render_claim(claim), "reason": reason})
            report.problems.append(_problem(render_claim(claim), "structured_claim", reason))

    # Second layer: every plant-specific token in the prose. It can only restrict.
    corpus = EvidenceCorpus(observations)
    covered = EvidenceCorpus([{"evidence": _covered_strings(report, index)}])
    question_terms = {c.key for c in extract_claims(question)}
    seen: set[tuple[str, str]] = set()
    anchors = len(report.supported)
    for token in extract_claims(prose):
        if (token.key, token.sentence) in seen:
            continue
        seen.add((token.key, token.sentence))
        report.checked += 1
        in_claims = covered.supports(token) or ("/" in token.text and all(key(p) in covered.terms for p in token.text.split("/")))
        in_evidence = corpus.supports(token) or ("/" in token.text and all(key(p) in corpus.terms for p in token.text.split("/")))
        if in_claims:
            continue
        if in_evidence:
            attribution = _attribution_problem(token, corpus) if token.kind == "value_with_unit" else None
            if attribution:
                report.problems.append(attribution)
            else:
                anchors += 1
                report.gaps.append(_problem(token.text, "unclaimed_value", "stated in the answer text without a structured claim", token.sentence))
        elif token.key in question_terms and DISCLAIMER.search(token.sentence):
            anchors += 1  # the user's own term, reported as not found / not confirmed
        else:
            reason = "appears only in the question and is stated as if it were a graph fact" if token.key in question_terms else "not found in any tool result"
            report.problems.append(_problem(token.text, token.kind, reason, token.sentence))
    claimed_keys = {key(s) for s in _covered_strings(report, index)}
    report.problems += [p for p in _role_problems(prose, corpus) if key(p["claim"].split(" ", 1)[1]) not in claimed_keys]

    for sentence in filter(None, (s.strip() for s in SENTENCE_SPLIT.split(prose.translate(TYPOGRAPHY)))):
        match = LIVE_STATE.search(sentence)
        if match and not DISCLAIMER.search(sentence):
            report.problems.append(_problem(match.group(0), "operating_state", "a P&ID does not contain current operating state; topology does not show what is open, running or flowing now", sentence))
    if protected_text and _quotes(prose, protected_text):
        report.problems.append(_problem("(instructions)", "prompt_disclosure", "the answer reproduces the agent's instructions"))

    if claims is None:
        report.gaps.append(_problem("(no claims block)", "missing_claims", "the answer did not include structured claims, so only the token-level check applied"))
    report.anchored = anchors > 0
    return report


def _quotes(text: str, protected: str) -> bool:
    squeezed, source = re.sub(r"\s+", " ", text), re.sub(r"\s+", " ", protected)
    return any(source[i : i + PROMPT_LEAK_LENGTH] in squeezed for i in range(0, max(len(source) - PROMPT_LEAK_LENGTH, 0), PROMPT_LEAK_LENGTH // 2))
