"""Post-generation grounding check.

Extracts plant-specific claims from an answer and verifies each against the facts returned
by the graph tools. Only claim-like tokens are checked, never ordinary prose:

* identifiers: tags, entity/connection ids, component codes, instrument numbers (any token
  mixing letters and digits), CamelCase type names
* DN values, line numbers and other bare numbers (3+ digits or decimals)
* numbers with engineering units

Two contextual checks catch a real value used in the wrong role: "line/segment/component/
nozzle X" must be a value of that kind of field, and a number with a unit must not be
attributed to a different property than the one that carries it.

A claim is supported when it appears in the tool results. Tool *inputs*, messages and
warnings are not evidence, because they echo what the user or the model wrote. A term that
appears only in the user's question (for example an assumed "DN100") is allowed solely in a
sentence that marks it as unverified, missing or not found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pid_agent.graph.entity_resolver import camel_tokens

EVIDENCE_SECTIONS = ("entities", "connections", "paths", "boundaries", "properties", "derived", "resolution", "evidence")
UNITS = (
    "m3/h", "m³/h", "kg/h", "l/min", "min-1", "mbar", "barg", "bar", "kPa", "MPa", "Pa", "psi",
    "°C", "°F", "kW", "MW", "m2", "m²", "m3", "m³", "mm", "cm", "km", "rpm", "kg", "%", "m",
)  # fmt: skip
_UNIT_PATTERN = "|".join(re.escape(u) for u in UNITS)
NUMBER_WITH_UNIT = re.compile(rf"(?<![\w.])(-?\d+(?:\.\d+)?)\s?({_UNIT_PATTERN})(?![\w/])")
DN_VALUE = re.compile(r"\bDN\s?\d+\b", re.IGNORECASE)
MIXED_TOKEN = re.compile(
    r"(?<![\w.\-/])(?=[\w.\-/]*\d)(?=[\w.\-/]*[A-Za-z])[A-Za-z0-9](?:[\w.\-/]*[A-Za-z0-9])?"
)
CAMEL_CASE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
BARE_NUMBER = re.compile(r"(?<![\w.])(?:\d+\.\d+|\d{3,})(?![\w]|\.\d)")
ORDINAL = re.compile(r"^\d+(?:st|nd|rd|th)$", re.IGNORECASE)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
DISCLAIMER = re.compile(
    r"n't|\b(?:not|no|cannot|unable|unverified|unconfirmed|hypothetical\w*|assum\w*|"
    r"suggest\w*|similar|candidates?|did you mean|rather than|instead|absent|missing|without|"
    r"unknown|you (?:said|stated|mentioned|asked|wrote)|your|if)\b",
    re.IGNORECASE,
)
# "<role word> <identifier>": the identifier must be a value of one of these evidence fields.
ROLE_FIELDS = {
    "line": ("linenumber", "line_id"),
    "segment": ("segmentnumber", "segment_id"),
    "component": ("pipingcomponentnumber", "pipingcomponentname", "linecomponent"),
    "nozzle": ("sub_tag", "subtagname"),
    "chamber": ("chamber_id", "chamber", "entered_chamber", "blocked_chamber"),
    "connection": ("blocked_connection",),
}
# An object id may stand in a role only if it is that kind of object.
ROLE_ID_PREFIX = {"line": "pipingnetworksystem-", "segment": "pipingnetworksegment-", "nozzle": "nozzle-", "chamber": "chamber-"}
ROLE_REFERENCE = re.compile(
    r"\b(line|segment|component|nozzle|chamber|connection)s?\s+(?:number\s+|no\.?\s*|#\s*)?[*_`]*([A-Za-z0-9][\w.\-/]*)", re.IGNORECASE
)
# Words too common in property names to tell one property from another.
GENERIC_PROPERTY_WORDS = {"design", "upper", "lower", "limit", "nominal", "representation", "numerical", "value", "type", "standard", "number", "code"}
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("value_with_unit", NUMBER_WITH_UNIT),
    ("nominal_diameter", DN_VALUE),
    ("identifier", MIXED_TOKEN),
    ("type_name", CAMEL_CASE),
    ("number", BARE_NUMBER),
)


# Models like typographic minus signs, non-breaking hyphens and narrow spaces.
TYPOGRAPHY = str.maketrans({"\u2212": "-", "\u2011": "-", "\u2010": "-", "\u202f": " ", "\u00a0": " ", "\u2009": " "})


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold()).strip(".,;:")


# Any character an identifier token cannot contain ends one (see MIXED_TOKEN), for example the
# superscripts in "PIS⁺Z⁺A275003". Evidence is cut at the same characters, so both sides agree.
IDENTIFIER_BOUNDARY = re.compile(r"[^\w.\-/]+")


def identifier_pieces(text: str) -> set[str]:
    """The normalized pieces of ``text`` that an answer token can match: the whole string and its parts."""
    pieces = set()
    for token in {*re.split(r"[\s,;()>=']+", text), *IDENTIFIER_BOUNDARY.split(text)}:
        pieces |= {token, *token.split("/"), *token.split("-"), *re.split(r"[/\-]", token)}
    return {p for p in map(_normalize, pieces) if p}


def _unit(unit: str) -> str:
    return unit.casefold().replace("³", "3").replace("²", "2")


DASHES = "-\u2013\u2014\u2212\u2011"


@dataclass(frozen=True)
class Claim:
    text: str
    kind: str
    sentence: str
    # A dash directly before a number may be a minus sign or just punctuation ("up to –1.0 bar",
    # "| – 1.0 bar"); such a value is accepted with either sign.
    after_dash: bool = False

    @property
    def key(self) -> str:
        return _normalize(self.text)


@dataclass
class GroundingReport:
    claims_checked: int = 0
    unsupported: list[dict[str, Any]] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return not self.unsupported


class EvidenceCorpus:
    """Every string and number that the graph tools returned."""

    def __init__(self, observations: list[dict[str, Any]]) -> None:
        self.terms: set[str] = set()
        self.numbers: set[float] = set()
        self.quantities: set[tuple[float, str]] = set()
        self.fields: dict[str, set[str]] = {}  # field name -> values seen under it
        self.ids: set[str] = set()
        self.connection_ids: set[str] = set()
        self.quantity_fields: dict[tuple[float, str], set[str]] = {}  # value -> property names
        for result in observations:
            for section in EVIDENCE_SECTIONS:
                self._walk(result.get(section))
            for key in ("stopped_at", "endpoints", "unexplored_beyond_max_depth"):
                self._walk(result.get("meta", {}).get(key))

    def _walk(self, node: Any) -> None:
        if node is None or isinstance(node, bool):
            return
        if isinstance(node, dict):
            if "property" in node and "value" in node:  # a get_properties item
                self._field(str(node["property"]), node["value"])
            if "id" in node and ("connection_type" in node or node.get("kind") in ("connection", "open_end")):
                self.connection_ids.add(_normalize(str(node["id"])))
            for key, value in node.items():
                if isinstance(value, dict) and "error" in value:
                    continue  # e.g. an unknown id echoed back by get_properties
                self._add(str(key))
                if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    self._field(str(key), value)
                self._walk(value)
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                self._walk(item)
        else:
            self._add(str(node))

    def _field(self, key: str, value: Any) -> None:
        text = str(value)
        self.fields.setdefault(_normalize(key), set()).add(_normalize(text))
        if key in ("id", "source", "target"):
            self.ids.add(_normalize(text))
        match = NUMBER_WITH_UNIT.fullmatch(text.strip())
        if match:
            self.quantity_fields.setdefault((float(match.group(1)), _unit(match.group(2))), set()).add(key)

    def role_values(self, role: str) -> set[str]:
        values: set[str] = set()
        for name in ROLE_FIELDS[role]:
            values |= self.fields.get(name, set())
        # A line/component reference such as "47127/C1" (an identifier, or part of an item's
        # name) establishes both the line and the component number.
        pairs = [t.split("/") for t in self.terms if t.count("/") == 1]
        if role == "line":
            values |= {line for line, _ in pairs}
        elif role == "component":
            values |= {component for _, component in pairs}
        return values

    def id_fits_role(self, role: str, key: str) -> bool:
        """Whether ``key`` is the id of an object of the kind the role word names."""
        if role == "connection":
            return key in self.connection_ids
        if key not in self.ids:
            return False
        if role == "component":
            return "/" not in key and not key.startswith(tuple(ROLE_ID_PREFIX.values()))
        return key.startswith(ROLE_ID_PREFIX[role]) and "/" not in key

    def _add(self, text: str) -> None:
        self.terms.add(_normalize(text))
        for match in NUMBER_WITH_UNIT.finditer(text):
            self.quantities.add((float(match.group(1)), _unit(match.group(2))))
        for piece in identifier_pieces(text):
            self.terms.add(piece)
            try:
                self.numbers.add(float(piece))
            except ValueError:
                pass

    def supports(self, claim: Claim) -> bool:
        if claim.key in self.terms:
            return True
        if claim.kind == "value_with_unit":
            match = NUMBER_WITH_UNIT.search(claim.text)
            if not match:
                return False
            value, unit = float(match.group(1)), _unit(match.group(2))
            if (value, unit) in self.quantities:
                return True
            return claim.after_dash and (-value, unit) in self.quantities
        if claim.kind == "number":
            return float(claim.text) in self.numbers
        return False


def extract_claims(text: str) -> list[Claim]:
    """Plant-specific claim tokens in ``text``, each with the sentence it occurs in."""
    claims: list[Claim] = []
    text = text.translate(TYPOGRAPHY)
    for sentence in filter(None, (s.strip() for s in SENTENCE_SPLIT.split(text))):
        remaining = sentence
        for kind, pattern in PATTERNS:
            for match in pattern.finditer(remaining):
                token = match.group(0)
                if kind == "identifier" and ORDINAL.match(token):
                    continue
                before = remaining[: match.start()].rstrip()
                claims.append(Claim(token, kind, sentence, after_dash=before[-1:] in DASHES and bool(before)))
            remaining = pattern.sub(lambda m: " " * len(m.group(0)), remaining)
    return claims


def _role_problems(answer: str, corpus: EvidenceCorpus) -> list[dict[str, Any]]:
    """Identifiers that exist in the evidence but not in the role the answer gives them."""
    problems = []
    for sentence in filter(None, (s.strip() for s in SENTENCE_SPLIT.split(answer.translate(TYPOGRAPHY)))):
        for match in ROLE_REFERENCE.finditer(sentence):
            role, token = match.group(1).lower(), match.group(2).rstrip(".,;:")
            key = _normalize(token)
            if not any(ch.isdigit() for ch in token) or key not in corpus.terms:
                continue  # prose ("line number"), or already reported as unsupported
            allowed = corpus.role_values(role)
            named = _normalize(role + token) in corpus.terms  # e.g. a sub-tag "Chamber 1"
            if key in allowed or key.split("/")[0] in allowed or named or corpus.id_fits_role(role, key):
                continue
            problems.append({
                "claim": f"{role} {token}",
                "kind": "identifier_role",
                "reason": f"'{token}' appears in the tool results, but not as a {role}",
                "sentence": sentence,
            })
    return problems


def _property_words(name: str) -> set[str]:
    return set(camel_tokens(name)) - GENERIC_PROPERTY_WORDS


def _attribution_problem(claim: Claim, corpus: EvidenceCorpus) -> dict[str, Any] | None:
    """A real value described with the words of a different property than the one carrying it."""
    match = NUMBER_WITH_UNIT.search(claim.text)
    if not match:
        return None
    value, unit = float(match.group(1)), _unit(match.group(2))
    carriers = corpus.quantity_fields.get((value, unit)) or (corpus.quantity_fields.get((-value, unit)) if claim.after_dash else None)
    if not carriers:
        return None
    words = set(re.findall(r"[a-z]+", claim.sentence.lower()))
    if any(_property_words(name) and _property_words(name) <= words for name in carriers):
        return None
    others = {name for names in corpus.quantity_fields.values() for name in names} - carriers
    wrong = sorted(name for name in others if _property_words(name) and _property_words(name) <= words)
    if not wrong:
        return None
    return {
        "claim": claim.text,
        "kind": "value_attribution",
        "reason": f"this value belongs to {', '.join(sorted(carriers))} in the tool results, but the sentence describes {', '.join(wrong)}",
        "sentence": claim.sentence,
    }


def check_grounding(answer: str, question: str, observations: list[dict[str, Any]]) -> GroundingReport:
    corpus = EvidenceCorpus(observations)
    question_terms = {claim.key for claim in extract_claims(question)}
    report = GroundingReport()
    seen: set[tuple[str, str]] = set()
    for claim in extract_claims(answer):
        if (claim.key, claim.sentence) in seen:
            continue
        seen.add((claim.key, claim.sentence))
        report.claims_checked += 1
        if corpus.supports(claim):
            problem = _attribution_problem(claim, corpus) if claim.kind == "value_with_unit" else None
            if problem:
                report.unsupported.append(problem)
            continue
        if claim.key in question_terms:
            if DISCLAIMER.search(claim.sentence):
                continue  # the user's own term, mentioned as unverified / not found
            reason = "appears only in the question and is stated as if it were a graph fact"
        else:
            reason = "not found in any tool result"
        report.unsupported.append(
            {"claim": claim.text, "kind": claim.kind, "reason": reason, "sentence": claim.sentence}
        )
    report.unsupported += _role_problems(answer, corpus)
    return report
