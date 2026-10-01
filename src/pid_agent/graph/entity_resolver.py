"""Deterministic entity resolution.

Tiers, tried in order; the first tier that yields a match wins:

1. ``exact_tag``             the query is exactly a tagName
2. ``tag_case_insensitive``  same, ignoring case
3. ``proteus_id``            the query is an entity id
4. ``identifier``            the query equals any identifier after normalisation
                             (position number, component code/number, instrument numbers, ...)
5. ``embedded_identifier``   identifiers found inside a longer phrase ("pump P4711",
                             "C1 on line 47126"); other words may narrow by type or line
6. ``type``                  the phrase names a type ("heat exchanger", "all pumps")

Nothing is ever bound by fuzzy matching: near misses are returned as ``suggestions`` only.
An identifier shared by several entities yields all of them with ``ambiguous = True``.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from pid_agent.models import Entity

TIER_CONFIDENCE = {
    "exact_tag": 1.0,
    "tag_case_insensitive": 0.98,
    "proteus_id": 0.98,
    "identifier": 0.95,
    "embedded_identifier": 0.9,
    "type": 0.8,
}
STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "at", "to", "and", "or", "for", "with", "from", "is",
    "are", "what", "which", "please", "list", "show", "find", "me", "all", "every", "each", "any",
}  # fmt: skip
QUANTIFIERS = {"all", "every", "each", "any"}
CATEGORY_WORDS = {
    "equipment": [("equipment",)],
    "piping_component": [("piping", "component")],
    "instrumentation": [("instrumentation",), ("instrument",)],
    "piping_line": [("line",)],
}
MAX_NGRAM = 3
SUGGESTION_CUTOFF = 0.75
MAX_SUGGESTIONS = 5


def normalize_identifier(text: str) -> str:
    """Case- and punctuation-insensitive form used to compare identifiers."""
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def camel_tokens(name: str) -> tuple[str, ...]:
    return tuple(t.lower() for t in re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", name))


def singular(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


@dataclass(frozen=True)
class Match:
    entity_id: str
    tier: str
    confidence: float
    matched_field: str
    matched_value: str
    identifier_kind: str = "source_identifier"
    identifier_origin: str | None = None

    @property
    def reason(self) -> str:
        """States how the match was obtained; never presents a derived value as a source field."""
        base = f"{self.matched_field} = {self.matched_value!r}"
        if self.identifier_kind == "derived_identifier":
            return f"derived identifier {base} ({self.identifier_origin}); not a literal field in the DEXPI file"
        if self.identifier_kind == "alias":
            return f"alias {base} ({self.identifier_origin})"
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_tier": self.tier,
            "confidence": self.confidence,
            "match_reason": self.reason,
            "identifier_kind": self.identifier_kind,
        }


@dataclass
class Resolution:
    query: str
    matches: list[Match] = field(default_factory=list)
    ambiguous: bool = False
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.matches:
            return "none"
        return "unique" if len(self.matches) == 1 else "multiple"

    @property
    def entity_ids(self) -> list[str]:
        return [m.entity_id for m in self.matches]


class EntityResolver:
    def __init__(self, entities: dict[str, Entity]) -> None:
        self._entities = entities
        self._tags: dict[str, str] = {}
        self._identifiers: dict[str, list[tuple[str, str, str]]] = {}
        self._type_phrases: dict[tuple[str, ...], set[str]] = {}
        for entity in entities.values():
            if entity.tag:
                self._tags[entity.tag] = entity.id
            self._add_identifier(entity.id, "id", entity.id)
            for key, value in entity.identifiers.items():
                self._add_identifier(entity.id, key, value)
            names = [camel_tokens(n) for n in entity.type_hierarchy]
            names += CATEGORY_WORDS[entity.category]
            for tokens in names:
                for size in range(1, len(tokens) + 1):
                    for start in range(len(tokens) - size + 1):
                        phrase = tokens[start : start + size]
                        self._type_phrases.setdefault(phrase, set()).add(entity.id)

    def _add_identifier(self, entity_id: str, key: str, value: str) -> None:
        self._identifiers.setdefault(normalize_identifier(value), []).append(
            (entity_id, key, value)
        )

    # ------------------------------------------------------------- type API
    def entities_of_type(self, phrase: str) -> set[str] | None:
        """Entity ids matching a type phrase, or None if the phrase is not a known type."""
        tokens = tuple(singular(t) for t in camel_tokens(phrase.replace("_", " ")))
        return self._type_phrases.get(tokens)

    def type_catalogue(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entity in self._entities.values():
            counts[entity.type] = counts.get(entity.type, 0) + 1
        return dict(sorted(counts.items()))

    # ------------------------------------------------------------ resolving
    def resolve(self, query: str, entity_type: str | None = None) -> Resolution:
        resolution = Resolution(query=query)
        text = (query or "").strip()
        if text:
            self._resolve_text(text, resolution)
        elif not entity_type:
            resolution.warnings.append("Empty query.")
        if entity_type:
            self._apply_type_argument(entity_type, resolution, had_query=bool(text))
        if not resolution.matches and text:
            resolution.suggestions = self._suggest(text)
        return resolution

    def _resolve_text(self, text: str, resolution: Resolution) -> None:
        whole = self._match_whole(text)
        if whole:
            resolution.matches = whole
            resolution.ambiguous = len(whole) > 1
            return
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.\-/]*", text)
        consumed = self._match_embedded(tokens, resolution)
        if not resolution.matches:
            self._match_types(tokens, consumed, resolution)

    def _match_whole(self, text: str) -> list[Match]:
        if text in self._tags:
            return [self._match(self._tags[text], "exact_tag", "tagName", text)]
        for tag, entity_id in self._tags.items():
            if tag.casefold() == text.casefold():
                return [self._match(entity_id, "tag_case_insensitive", "tagName", tag)]
        for entity_id in self._entities:
            if entity_id.casefold() == text.casefold():
                return [self._match(entity_id, "proteus_id", "id", entity_id)]
        return self._identifier_matches(text, "identifier")

    def _identifier_matches(self, text: str, tier: str) -> list[Match]:
        key = normalize_identifier(text)
        if len(key) < 2:
            return []
        seen: dict[str, Match] = {}
        for entity_id, name, value in self._identifiers.get(key, []):
            seen.setdefault(entity_id, self._match(entity_id, tier, name, value))
        return list(seen.values())

    def _match(self, entity_id: str, tier: str, name: str, value: str) -> Match:
        if tier == "type":
            return Match(entity_id, tier, TIER_CONFIDENCE[tier], name, value, "type")
        origin = self._entities[entity_id].origin_of(name)
        return Match(entity_id, tier, TIER_CONFIDENCE[tier], name, value, origin.kind, origin.origin)

    def _match_embedded(self, tokens: list[str], resolution: Resolution) -> set[int]:
        """Find identifiers inside the phrase. Returns the indexes of consumed tokens."""
        consumed: set[int] = set()
        terms: list[list[Match]] = []
        for size in range(min(MAX_NGRAM, len(tokens)), 0, -1):
            for start in range(len(tokens) - size + 1):
                span = range(start, start + size)
                if consumed.intersection(span):
                    continue
                if size == 1 and tokens[start].casefold() in STOPWORDS:
                    continue
                hits = self._identifier_matches(" ".join(tokens[i] for i in span), "embedded_identifier")
                if hits:
                    consumed.update(span)
                    terms.append(hits)
        if not terms:
            return consumed

        line_terms = [t for t in terms if all(self._is_line(m.entity_id) for m in t)]
        item_terms = [t for t in terms if t not in line_terms]
        used_line_context = False
        if item_terms and line_terms:
            lines = {
                self._entities[m.entity_id].identifiers.get("lineNumber")
                for term in line_terms
                for m in term
            }
            narrowed = [[m for m in term if self._line_of(m.entity_id) in lines] for term in item_terms]
            if all(narrowed):
                item_terms, line_terms, used_line_context = narrowed, [], True
            else:
                used_line_context = True  # the word "line" must not narrow to the line alone
                resolution.warnings.append(
                    "The line number and the other identifier(s) in the query do not refer to "
                    "the same item; returning both."
                )
        matches = {m.entity_id: m for term in item_terms + line_terms for m in term}
        resolution.matches = list(matches.values())
        resolution.ambiguous = any(len(term) > 1 for term in item_terms + line_terms)
        self._narrow_by_type_words(tokens, consumed, resolution, used_line_context)
        return consumed

    def _narrow_by_type_words(
        self, tokens: list[str], consumed: set[int], resolution: Resolution, used_line: bool
    ) -> None:
        for phrase, ids in self._type_phrases_in(tokens, consumed):
            if used_line and all(self._is_line(i) for i in ids):
                continue
            kept = [m for m in resolution.matches if m.entity_id in ids]
            if kept:
                resolution.matches = kept
                if len(kept) == 1:
                    resolution.ambiguous = False
            else:
                found = ", ".join(f"{m.entity_id} ({self._entities[m.entity_id].type})" for m in resolution.matches)
                resolution.warnings.append(
                    f"The query says '{' '.join(phrase)}' but the identifier matches {found}."
                )

    def _type_phrases_in(
        self, tokens: list[str], consumed: set[int]
    ) -> list[tuple[tuple[str, ...], set[str]]]:
        """Longest-first, non-overlapping type phrases among unconsumed tokens."""
        lowered = [singular(t.casefold()) for t in tokens]
        found: list[tuple[int, tuple[str, ...], set[str]]] = []
        for size in range(min(MAX_NGRAM, len(tokens)), 0, -1):
            for start in range(len(tokens) - size + 1):
                span = range(start, start + size)
                if consumed.intersection(span):
                    continue
                phrase = tuple(lowered[i] for i in span)
                ids = self._type_phrases.get(phrase)
                if ids:
                    consumed.update(span)
                    found.append((start, phrase, ids))
        return [(phrase, ids) for _, phrase, ids in sorted(found)]

    def _match_types(self, tokens: list[str], consumed: set[int], resolution: Resolution) -> None:
        phrases = self._type_phrases_in(tokens, consumed)
        if not phrases:
            return
        matches: dict[str, Match] = {}
        for phrase, ids in phrases:
            for entity_id in ids:
                matches.setdefault(entity_id, self._match(entity_id, "type", "type", " ".join(phrase)))
        resolution.matches = [matches[i] for i in self._entities if i in matches]
        lowered = [t.casefold() for t in tokens]
        is_set_query = bool(QUANTIFIERS.intersection(lowered)) or any(
            singular(t) != t and (singular(t),) in self._type_phrases for t in lowered
        )
        resolution.ambiguous = len(resolution.matches) > 1 and not is_set_query
        unknown = [
            tokens[i] for i in range(len(tokens))
            if i not in consumed and lowered[i] not in STOPWORDS
        ]
        if unknown:
            resolution.warnings.append(
                "These words were not matched against the graph and did not narrow the "
                f"result: {', '.join(unknown)}."
            )
            resolution.ambiguous = len(resolution.matches) > 1

    def _apply_type_argument(self, entity_type: str, resolution: Resolution, had_query: bool) -> None:
        ids = self.entities_of_type(entity_type)
        by_identifier = bool(resolution.matches) and all(m.tier != "type" for m in resolution.matches)
        if ids is None:
            message = f"Unknown entity_type '{entity_type}'. Known types: {', '.join(self.type_catalogue())}."
            if by_identifier:
                # The identifier is the stronger signal; a wrong type word must not hide it.
                resolution.warnings.append(message + " The type filter was ignored.")
                return
            resolution.matches = []
            resolution.ambiguous = False
            resolution.warnings.append(message)
            return
        if not had_query:
            resolution.matches = [
                self._match(i, "type", "type", entity_type) for i in self._entities if i in ids
            ]
            return
        kept = [m for m in resolution.matches if m.entity_id in ids]
        if resolution.matches and not kept:
            found = ", ".join(f"{m.entity_id} ({self._entities[m.entity_id].type})" for m in resolution.matches)
            if by_identifier:
                resolution.warnings.append(
                    f"entity_type '{entity_type}' does not fit the identifier match {found}; "
                    "the match is returned anyway."
                )
                return
            resolution.warnings.append(f"Matches were found, but none is of type '{entity_type}'.")
        resolution.matches = kept
        resolution.ambiguous = resolution.ambiguous and len(kept) > 1

    def _suggest(self, text: str) -> list[dict[str, Any]]:
        candidates = {normalize_identifier(text)}
        candidates.update(normalize_identifier(t) for t in re.findall(r"\S*\d\S*", text))
        scored: dict[str, tuple[float, str, str]] = {}
        for candidate in filter(None, candidates):
            for key, entries in self._identifiers.items():
                score = difflib.SequenceMatcher(None, candidate, key).ratio()
                if score < SUGGESTION_CUTOFF:
                    continue
                for entity_id, name, value in entries:
                    if score > scored.get(entity_id, (0.0, "", ""))[0]:
                        scored[entity_id] = (score, name, value)
        ranked = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))[:MAX_SUGGESTIONS]
        return [
            {"id": entity_id, "similar_to": f"{name} = {value!r}", "similarity": round(score, 2)}
            for entity_id, (score, name, value) in ranked
        ]

    def _is_line(self, entity_id: str) -> bool:
        return self._entities[entity_id].category == "piping_line"

    def _line_of(self, entity_id: str) -> str | None:
        return (self._entities[entity_id].piping_context or {}).get("lineNumber")
