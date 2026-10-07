"""Application wording for the status of a tool result.

A tool's own message can repeat its input ("No entity matches '<query>'"), and the model
chooses that input. If such a message were shown as evidence, a model could put any sentence
into a lookup and have it printed in the answer. So a status shown to the user is written
here, from fixed templates, and a value is inserted only when its provenance is established:

* it occurs in the user's question as whole words, or
* it is canonical graph data: an id, a name, a tag, an identifier, a type or a line number
  that exists in the graph, compared whole, or
* it is one of the tool's own enumerated options (a direction, a relationship).

Nothing is filtered or judged by its wording. A value either has a known origin or is left out.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

DIRECTIONS = {"downstream", "upstream", "both", "any"}
RELATIONSHIPS = {"piping", "instrumentation", "all"}


@dataclass(frozen=True)
class Provenance:
    """What may be shown: text of the user's question and names that exist in the graph.

    ``graph_names`` maps the comparison form of every graph name to the graph's own spelling.
    What is printed is always that canonical spelling, or the user's words as the user wrote
    them. The value a tool was called with is only ever compared, never printed.
    """

    question: str = ""
    graph_names: Mapping[str, str] = field(default_factory=dict)

    def canonical(self, value: Any) -> str | None:
        """The text to print for ``value``, or None if its origin is not established."""
        text = " ".join(str(value).split()) if isinstance(value, str) else ""
        if len(text) < 2:
            return None
        if text.casefold() in self.graph_names:
            return self.graph_names[text.casefold()]
        return self._from_question(text)

    def _from_question(self, text: str) -> str | None:
        """The run of whole words of the question that ``text`` matches, as the user wrote it.

        Whole words, not characters: "safe to open" is not in "Is it unsafe to open?".
        """
        written = [word.strip(EDGE_PUNCTUATION) for word in self.question.split()]
        written = [word for word in written if word]
        asked, wanted = [word.casefold() for word in written], _words(text)
        for start in range(len(asked) - len(wanted) + 1):
            if wanted and asked[start : start + len(wanted)] == wanted:
                return " ".join(written[start : start + len(wanted)])
        return None

    def shows(self, value: Any) -> bool:
        return self.canonical(value) is not None

    def quoted(self, value: Any) -> str:
        """`` '<canonical spelling>'`` when the value may be shown, otherwise nothing."""
        shown = self.canonical(value)
        return f" '{shown}'" if shown is not None else ""

    def named(self, value: Any, otherwise: str) -> str:
        return self.canonical(value) or otherwise


EDGE_PUNCTUATION = ".,;:!?\"'()[]{}"


def _words(text: str) -> list[str]:
    """Lower-cased words, without the punctuation around them ("T4750?" and "T4750" are one word)."""
    return [word for word in (token.strip(EDGE_PUNCTUATION).casefold() for token in text.split()) if word]


def _ids(items: list[Any], provenance: Provenance) -> list[str]:
    return [shown for shown in (provenance.canonical(i) for i in items) if shown is not None]


def _nothing_reached(given: dict[str, Any], meta: dict[str, Any], provenance: Provenance) -> str:
    """An empty traversal, with the conditions that decide what it shows.

    A complete search can show that nothing is connected. A search that was cut off at its depth
    limit, told to stop at certain types, or filtered by a type the graph does not have, shows
    only that nothing was found within those limits.
    """
    start = provenance.named(meta.get("start") or given.get("start_entity_id"), "the requested item")
    direction = {"downstream": "downstream of", "upstream": "upstream of", "both": "connected to (flow direction ignored)"}.get(given.get("direction"), "from")
    closed = _ids(meta.get("blocked") or [], provenance)
    conditions = f" with {', '.join(closed)} treated as closed" if closed else ""
    types = (meta.get("type_filter") or {}).get("applied") or []
    shown = _ids(types, provenance)
    what = f"of type {', '.join(shown)}" if types and len(shown) == len(types) else "of the requested type(s)" if types else "at all"
    unknown, stops, depth = (meta.get("type_filter") or {}).get("unknown"), meta.get("stopped_at_types"), meta.get("max_depth")
    if meta.get("truncated_by_max_depth"):
        return f"Nothing {what} was found within {depth} pipe(s) {direction} {start}{conditions}. The search stopped at that depth, so this does not show that nothing lies beyond."
    if unknown or stops:
        why = "its type filter named a type that is not in the graph" if unknown else "it was told to stop at certain types"
        return f"Nothing {what} was found {direction} {start}{conditions}, but the search was limited ({why}), so this does not show that nothing is connected."
    leaves = _ids([e.get("id") for e in meta.get("endpoint_details") or [] if e.get("kind") == "drawing_end"], provenance)
    beyond = f" The piping leaves this drawing at {', '.join(leaves)}; what is connected beyond is not shown." if leaves else ""
    return f"Nothing {what} is {direction} {start}{conditions}. The search covered all the drawn piping in that direction" + (" (no type filter)." if not types else ".") + beyond


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
        asked = provenance.quoted(given.get("query"))
        return f"No matching entity was found in the P&ID graph{' for' + asked if asked else ''}."
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
        return _nothing_reached(given, meta, provenance)
    if tool == "isolation_boundary":
        return f"{item} has no piping connections, so it has no isolation boundary."
    if tool == "trace_instrumentation":
        return f"{item} has no instrumentation links."
    return "The graph call returned no result."
