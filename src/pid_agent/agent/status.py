"""Application wording for the status of a tool result.

A tool's own message can repeat its input ("No entity matches '<query>'"), and the model
chooses that input. If such a message were shown as evidence, a model could put any sentence
into a lookup and have it printed in the answer. So a status shown to the user is written
here, from fixed templates, and a value is inserted only when its provenance is established:

* it occurs in the user's question, or
* it is canonical graph data: an id, a name, a tag, an identifier, a type or a line number
  that exists in the graph, compared whole, or
* it is one of the tool's own enumerated options (a direction, a relationship).

Nothing is filtered or judged by its wording. A value either has a known origin or is left out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DIRECTIONS = {"downstream", "upstream", "both", "any"}
RELATIONSHIPS = {"piping", "instrumentation", "all"}


@dataclass(frozen=True)
class Provenance:
    """What may be shown: text of the user's question and names that exist in the graph."""

    question: str = ""
    graph_names: frozenset[str] = frozenset()

    def shows(self, value: Any) -> bool:
        text = " ".join(str(value).split()) if isinstance(value, str) else ""
        if len(text) < 2:
            return False
        return text.casefold() in self.graph_names or text.casefold() in " ".join(self.question.split()).casefold()

    def quoted(self, value: Any) -> str:
        """`` '<value>'`` when it may be shown, otherwise nothing."""
        return f" '{' '.join(str(value).split())}'" if self.shows(value) else ""

    def named(self, value: Any, otherwise: str) -> str:
        return " ".join(str(value).split()) if self.shows(value) else otherwise


def _ids(items: list[Any], provenance: Provenance) -> list[str]:
    return [str(i) for i in items if provenance.shows(i)]


def status_statement(result: dict[str, Any], provenance: Provenance) -> str | None:
    """What a result with no rows says, in fixed wording. None when it has nothing to say."""
    status, tool = result.get("status"), result.get("tool", "")
    if status not in ("not_found", "ambiguous", "empty", "error"):
        return None
    given, meta = result.get("input") or {}, result.get("meta") or {}
    if status == "error":
        return "A graph call was not valid and returned nothing."
    if status == "ambiguous":
        candidates = _ids([e.get("id") for e in result.get("entities") or []], provenance)
        asked = provenance.quoted(given.get("query") or given.get("entity_id"))
        return f"The lookup{asked} matches {len(candidates) or 'several'} entities and none was selected" + (f": {', '.join(candidates)}." if candidates else ".")
    if tool == "find_path" and meta.get("no_path"):
        missing = meta["no_path"]
        direction = missing["direction"] if missing.get("direction") in DIRECTIONS else "piping"
        closed = _ids(missing.get("blocked") or [], provenance)
        ends = (provenance.named(missing.get("source"), "the first item"), provenance.named(missing.get("target"), "the second item"))
        return f"No {direction} piping path from {ends[0]} to {ends[1]} exists in the P&ID graph" + (f" with {', '.join(closed)} treated as closed." if closed else ".")
    if tool == "find_entities":
        return f"No matching entity was found in the P&ID graph{' for' + provenance.quoted(given.get('query')) if provenance.shows(given.get('query')) else ''}."
    if tool == "list_entities":
        kind = provenance.quoted(given.get("entity_type"))
        return f"No entity of type{kind} with the requested property value exists in the P&ID graph." if given.get("property_filter") else f"The requested type{kind} is not present in the P&ID graph."
    if tool == "get_properties":
        return "None of the given ids exists in the P&ID graph." if status == "not_found" else "The requested properties are not present in the P&ID graph for these objects."
    if tool == "trace_line":
        return f"No piping line{provenance.quoted(given.get('line'))} exists in the P&ID graph."
    item = provenance.named(given.get("entity_id") or given.get("start_entity_id"), "The requested item")
    if status == "not_found":
        return f"{item} does not exist in the P&ID graph." if item != "The requested item" else "The requested item does not exist in the P&ID graph."
    if tool == "get_connections":
        relationship = given.get("relationship") if given.get("relationship") in RELATIONSHIPS - {"all"} else ""
        direction = f" in direction {given['direction']}" if given.get("direction") in DIRECTIONS - {"both"} else ""
        return f"{item} has no {relationship + ' ' if relationship else ''}connections{direction}."
    if tool == "traverse":
        direction = given.get("direction") if given.get("direction") in DIRECTIONS else "in that direction"
        closed = _ids(meta.get("blocked") or [], provenance)
        return f"No matching entities were found {direction} of {item[0].lower() + item[1:] if item == 'The requested item' else item}" + (f" with {', '.join(closed)} treated as closed." if closed else ".")
    if tool == "isolation_boundary":
        return f"{item} has no piping connections, so it has no isolation boundary."
    if tool == "trace_instrumentation":
        return f"{item} has no instrumentation links."
    return "The graph call returned no result."
