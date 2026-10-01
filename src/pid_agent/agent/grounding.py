"""Post-generation grounding check.

Extracts plant-specific claims from an answer and verifies each against the facts returned
by the graph tools. Only claim-like tokens are checked, never ordinary prose:

* identifiers: tags, entity/connection ids, component codes, instrument numbers (any token
  mixing letters and digits), CamelCase type names
* DN values, line numbers and other bare numbers (3+ digits or decimals)
* numbers with engineering units

A claim is supported when it appears in the tool results. Tool *inputs*, messages and
warnings are not evidence, because they echo what the user or the model wrote. A term that
appears only in the user's question (for example an assumed "DN100") is allowed solely in a
sentence that marks it as unverified, missing or not found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

EVIDENCE_SECTIONS = ("entities", "connections", "paths", "properties", "resolution", "evidence")
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
        for result in observations:
            for section in EVIDENCE_SECTIONS:
                self._walk(result.get(section))
            self._walk(result.get("meta", {}).get("stopped_at"))

    def _walk(self, node: Any) -> None:
        if node is None or isinstance(node, bool):
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, dict) and "error" in value:
                    continue  # e.g. an unknown id echoed back by get_properties
                self._add(str(key))
                self._walk(value)
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                self._walk(item)
        else:
            self._add(str(node))

    def _add(self, text: str) -> None:
        self.terms.add(_normalize(text))
        for match in NUMBER_WITH_UNIT.finditer(text):
            self.quantities.add((float(match.group(1)), _unit(match.group(2))))
        for token in re.split(r"[\s,;()>=']+", text):
            for piece in {token, *token.split("/"), *token.split("-"), *re.split(r"[/\-]", token)}:
                piece = _normalize(piece)
                if not piece:
                    continue
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
    return report
