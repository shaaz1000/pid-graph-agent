"""Structured final answers.

The model does not write the answer. It calls ``submit_answer`` with the evidence ids that
answer the question and with what the P&ID does not establish. This module then

* checks that every id exists (a set lookup, no reading of prose),
* decides for each cited row whether it is a *direct* fact (read from the drawing) or a
  *derived* fact (computed by a graph operation); that is a property of the tool result, not
  the model's opinion,
* writes the answer from the rows and from the categories of the unknowns, and
* reduces it to canonical facts, which is what answers are compared by.

No text the model writes reaches the answer. A summary or the note of an unknown is kept in
the run record for debugging; it is not shown, not checked and not scored, so it cannot carry
an unsupported claim to the user.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pid_agent.agent.claims import build_facts
from pid_agent.agent.evidence_refs import _status_text, render_rows
from pid_agent.agent.status import Provenance
from pid_agent.agent.tools import SubmitAnswerArgs

# Tools whose every row is computed by a graph algorithm rather than read from one object.
DERIVED_TOOLS = {"traverse", "find_path"}
ROW_SECTIONS = ("entities", "connections", "paths", "boundaries", "derived")
# What each category of unknown says. Written here, once; the model only picks the category.
UNKNOWN_STATEMENTS = {
    "operating_procedure": "A P&ID does not contain operating procedures or sequences, such as the order in which to operate valves.",
    "operating_state": "A P&ID does not show operating state: which valves are open or closed, or what is running or flowing.",
    "process_behaviour": "A P&ID does not establish how pressure, flow, level or temperature would respond; that needs process data and calculation.",
    "design_adequacy": "A P&ID does not establish whether a design is adequate or safe, for example whether relief capacity is sufficient.",
    "off_drawing": "What lies beyond an off-page connector or an open-ended pipe is not on this drawing.",
    "not_represented": "The drawing does not contain an item or attribute that the question asks for.",
    "purpose_or_intent": "A P&ID does not state the purpose of an item or the intent of a design.",
    "ambiguous_request": "The question does not identify a single item in the drawing.",
    "other": "Part of the question is not established by the P&ID.",
}
# Which qualifiers of a legacy typed fact identify it (the rest is provenance or detail).
FACT_KEYS = {
    "has_property": ("property",),
    "lacks_property": ("property",),
    "flows_to": ("lineNumber", "nominalDiameterRepresentation"),
    "open_end": ("lineNumber", "missing_end"),
    "reaches": ("direction",),
    "path": ("entities", "direction"),
    "no_path": ("direction",),
    "chamber_boundary": ("entered_chamber", "blocked_chamber"),
}
SKIPPED_PREDICATES = {"identified_as"}  # names of an item are not findings about the plant
DERIVED_DROP = {"connection"}  # connection ids are provenance, not part of what was found


def _step(ref: str) -> int:
    digits = ref[1:].split(".")[0]
    return int(digits) if digits.isdigit() else 0


def canonical(predicate: str, subject: str | None, obj: str | None = None, value: Any = None, **qualifiers: Any) -> dict[str, Any]:
    """One fact in the form answers are compared by."""
    fact: dict[str, Any] = {"p": predicate, "s": subject}
    if obj is not None:
        fact["o"] = obj
    if value is not None:
        fact["v"] = value if isinstance(value, bool) else str(value)
    q = {k: v for k, v in qualifiers.items() if v not in (None, "", [], {})}
    if q:
        fact["q"] = q
    return fact


def fact_key(fact: dict[str, Any]) -> str:
    return json.dumps(fact, sort_keys=True, ensure_ascii=False, default=str)


class EvidenceRegistry:
    """Every citable row of the tool results: its kind, its wording and its canonical facts."""

    def __init__(self, observations: list[dict[str, Any]], provenance: Provenance | None = None) -> None:
        self.observations = observations
        # Decides which values a status row may show; nothing from a tool's input by default.
        self.provenance = provenance or Provenance()
        self._index = build_facts(observations)
        self._kind: dict[str, str] = {}
        self._derived: dict[str, dict[str, Any]] = {}
        self._tool: dict[str, str] = {}
        self._attributes: dict[str, list[dict[str, Any]]] = {}
        # Steps are numbered over everything the model did, so a result is found by its own id.
        self._by_step = {_step(r["result_ref"]): r for r in observations if r.get("result_ref")}
        self.entity_ids: set[str] = set()
        for result in observations:
            tool = result.get("tool", "")
            computed = tool in DERIVED_TOOLS
            for section in ROW_SECTIONS:
                for row in result.get(section) or []:
                    if row.get("ref"):
                        self._kind[row["ref"]] = "derived" if computed or section == "derived" else "direct"
                        self._tool[row["ref"]] = tool
                        if row.get("attributes"):
                            self._attributes[row["ref"]] = [{**a, "of": row["id"]} for a in row["attributes"]]
                        if section == "derived":
                            self._derived[row["ref"]] = row
            for report in (result.get("properties") or {}).values():
                if isinstance(report, dict) and "found" in report:
                    for item in report["found"]:
                        self._kind[item["ref"]] = "direct"
                    if report.get("missing_ref"):
                        self._kind[report["missing_ref"]] = "direct"
            if result.get("status_ref") and _status_text(result):
                self._kind[result["status_ref"]] = "derived" if computed else "direct"
                self._tool[result["status_ref"]] = tool
        for fact in self._index.facts:
            self.entity_ids.update(i for i in (fact.subject, fact.object) if i and i != "query")
        for row in self._derived.values():
            self.entity_ids.update(i for i in (row.get("subject"), row.get("object"), *row.get("source_entities", [])) if i)

    def rows(self, ref: str) -> list[tuple[str, str]] | None:
        """(wording, row id) for an evidence id; R<step> gives every row of that result."""
        return render_rows([ref], self.observations, self.provenance)

    def kind(self, row_ref: str) -> str:
        return self._kind.get(row_ref, "direct")

    def operation(self, row_ref: str) -> str | None:
        row = self._derived.get(row_ref)
        return row["operation"] if row else self._tool.get(row_ref) if self.kind(row_ref) == "derived" else None

    def all_facts(self) -> list[dict[str, Any]]:
        """Every canonical fact the tool results contain, cited or not."""
        seen: dict[str, dict[str, Any]] = {}
        for ref in self._kind:
            for fact in self.facts(ref):
                seen.setdefault(fact_key(fact), fact)
        return list(seen.values())

    def facts(self, row_ref: str) -> list[dict[str, Any]]:
        row = self._derived.get(row_ref)
        if row is not None:
            qualifiers = {k: v for k, v in (row.get("qualifiers") or {}).items() if k not in DERIVED_DROP}
            return [canonical(row["predicate"], row["subject"], row.get("object"), row.get("value"), **qualifiers)]
        meta = self._by_step.get(_step(row_ref), {}).get("meta") or {}
        out = []
        for fact in self._index.by_ref(row_ref):
            if fact.predicate in SKIPPED_PREDICATES:
                continue
            qualifiers = {name: fact.qualifiers.get(name) for name in FACT_KEYS.get(fact.predicate, ())}
            if fact.predicate in ("reaches", "path", "no_path") and meta.get("blocked"):
                qualifiers["blocked"] = meta["blocked"]
            # The subject is the object that carries the property (a nozzle, an actuator, a line
            # segment). The item it belongs to is kept beside it, so two nozzles of one pump
            # stay two facts and a fact can still be found by the item it was asked for.
            owner = fact.qualifiers.get("owner")
            if fact.predicate in ("has_property", "lacks_property") and owner and owner != fact.subject:
                qualifiers["owner"] = owner
            out.append(canonical(fact.predicate, fact.subject, fact.object, fact.value, **qualifiers))
        for item in self._attributes.get(row_ref, []):
            out.append(canonical("has_property", item.get("on") or item["of"], None, item["value"], property=item["property"], owner=item["of"] if item.get("on") else None))
        return out


@dataclass
class Submission:
    """A validated structured answer, ready to show and to compare."""

    direct: list[dict[str, Any]] = field(default_factory=list)    # ref, text, facts
    derived: list[dict[str, Any]] = field(default_factory=list)   # ref, text, facts, operation
    unknowns: list[dict[str, Any]] = field(default_factory=list)  # category, about (ids), about_names, note (log only)
    model_summary: str | None = None                              # log only: never shown, never scored
    requested: list[dict[str, Any]] = field(default_factory=list)  # id, description, kind, covered_by
    notes: list[str] = field(default_factory=list)   # what the application changed, and why
    errors: list[str] = field(default_factory=list)  # why the submission cannot be used

    @property
    def ok(self) -> bool:
        return not self.errors

    def facts(self) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for item in [*self.direct, *self.derived]:
            for fact in item["facts"]:
                seen.setdefault(fact_key(fact), fact)
        return list(seen.values())

    def to_dict(self) -> dict[str, Any]:
        return {"direct_facts": self.direct, "derived_facts": self.derived, "unknowns": self.unknowns, "requested_outputs": self.requested, "model_summary": self.model_summary, "notes": self.notes}

    def render(self) -> str:
        """The answer the user sees: cited rows and typed unknowns, every word written by code."""
        parts: list[str] = []
        if self.direct:
            parts.append("Facts in the drawing\n" + "\n".join(f"- {item['text']} [{item['ref']}]" for item in self.direct))
        if self.derived:
            parts.append("Derived by graph analysis of the drawing\n" + "\n".join(f"- {item['text']} [{item['ref']}, {item['operation']}]" for item in self.derived))
        if self.unknowns:
            lines = []
            for unknown in self.unknowns:
                about = f" Asked about: {', '.join(unknown['about_names'])}." if unknown.get("about_names") else ""
                lines.append(f"- {UNKNOWN_STATEMENTS[unknown['category']]}{about}")
            parts.append("Not established by the P&ID\n" + "\n".join(dict.fromkeys(lines)))
        return "\n\n".join(parts)


def render_submission(submission: dict[str, Any]) -> str:
    """The answer text for a stored submission (see ``Submission.to_dict``)."""
    return Submission(direct=submission["direct_facts"], derived=submission["derived_facts"], unknowns=submission["unknowns"]).render()


Resolver = Callable[[str], list[tuple[str, str]]]  # an id, tag or name -> the (id, name) it denotes


def validate_submission(arguments: dict[str, Any], observations: list[dict[str, Any]], resolve: Resolver | None = None, requested: list[dict[str, Any]] | None = None,
                        provenance: Provenance | None = None) -> Submission:
    """Check a ``submit_answer`` call against the tool results and build the answer from it.

    ``resolve`` turns what the model wrote in ``unknowns.about`` into entities, with the same
    deterministic resolver the tools use. Without it only ids from the tool results are accepted.

    ``provenance`` (the user's question and the names that exist in the graph) decides which
    values the status of an empty or failed lookup may show; a tool input is never shown just
    because a tool repeated it.

    ``requested`` is the decomposition of the question (ids q1, q2, ...). Every one of them
    must be covered by cited evidence or by an unknown. This checks that nothing asked was
    passed over; whether the evidence answers it is not judged here.
    """
    out = Submission()
    try:
        args = SubmitAnswerArgs(**arguments)
    except Exception as exc:  # pydantic reports what is wrong with the arguments
        problems = getattr(exc, "errors", lambda: [])()
        out.errors.append("Invalid submit_answer arguments: " + ("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in problems) or str(exc)))
        return out
    registry = EvidenceRegistry(observations, provenance)
    seen: set[str] = set()
    covered: dict[str, dict[str, list[str]]] = {}

    def cover(ids: list[str], kind: str, what: str) -> None:
        for output in ids:
            covered.setdefault(output.strip().casefold(), {"direct": [], "derived": [], "unknown": []})[kind].append(what)

    for cited in [*args.direct_facts, *args.derived_facts]:
        ref = cited.ref
        rows = registry.rows(str(ref).strip().strip("[]"))
        if rows is None:
            out.errors.append(f"'{ref}' is not an evidence id of any tool result. Use the ids exactly as the results give them.")
            continue
        for text, row_ref in rows:
            if row_ref in seen:
                continue
            seen.add(row_ref)
            item = {"ref": row_ref, "text": text, "facts": registry.facts(row_ref), "covers": cited.covers}
            if registry.kind(row_ref) == "derived":
                out.derived.append({**item, "operation": registry.operation(row_ref)})
            else:
                out.direct.append(item)
            cover(cited.covers, registry.kind(row_ref), row_ref)
    listed = {"direct": {c.ref for c in args.direct_facts}, "derived": {c.ref for c in args.derived_facts}}
    moved = sum(1 for kind, items in (("direct", out.derived), ("derived", out.direct)) for item in items if item["ref"] in listed[kind])
    if moved:
        out.notes.append(f"{moved} cited row(s) were listed under the other kind; whether a fact is direct or derived is decided by the tool result.")
    for unknown in args.unknowns:
        ids, names = [], []
        for text in unknown.about:
            matches = resolve(text) if resolve else [(text, text)] if text in registry.entity_ids else []
            if len(matches) == 1:
                ids.append(matches[0][0])
                names.append(matches[0][1] if matches[0][1] == matches[0][0] else f"{matches[0][1]} ({matches[0][0]})")
            elif matches:  # never pick one of several
                out.errors.append(f"unknowns.about: '{text}' matches several items ({', '.join(i for i, _ in matches)}). Use one entity id.")
            else:
                out.errors.append(f"unknowns.about: '{text}' does not name an item in the drawing. Use an entity id, a tag or a name from the tool results, or leave 'about' empty.")
        out.unknowns.append({"category": unknown.category, "about": ids, "about_names": names, "covers": unknown.covers, "note": unknown.note.strip()})
        cover(unknown.covers, "unknown", unknown.category)
    if not (out.direct or out.derived or args.unknowns) and not out.errors:
        out.errors.append("The answer cites no evidence and names no unknown. Cite the rows that answer the question, or name what the P&ID does not establish.")
    if requested:
        ids = [r["id"] for r in requested]
        if len(ids) == 1 and (out.direct or out.derived or out.unknowns):
            covered.setdefault(ids[0], {"direct": [], "derived": [], "unknown": []})  # one thing asked: whatever is submitted is about it
        for stray in sorted(set(covered) - set(ids)):
            out.errors.append(f"'covers' names {stray}, which is not a requested output. The requested outputs are {', '.join(ids)}.")
        for output in requested:
            if output["id"] not in covered:
                out.errors.append(f"Requested output {output['id']} ({output['description']}) has not been addressed. Provide supported evidence or mark it unknown.")
        out.requested = [{**r, "covered_by": covered.get(r["id"], {})} for r in requested]
    out.model_summary = (args.summary or "").strip() or None
    return out
