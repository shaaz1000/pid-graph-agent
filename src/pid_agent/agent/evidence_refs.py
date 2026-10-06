"""Evidence references and relationship-aware grounding of the answer text.

    tool result rows   --annotate_refs-->  E<step>.<n> per row, R<step> per result (set by code)
    answer sentence    --cites-->          "P4711 feeds H1007. [E2.2]"
    refs               --FactIndex-->      typed facts (subject, relation, value, qualifiers)
    sentence x facts   --check_answer-->   supported / unsupported, with the facts used

The model does not restate evidence; it points at it. Code then checks, sentence by sentence,
that what the sentence says is *associated* in the cited facts, not merely present somewhere:

* an identifier or value must be carried by a cited fact;
* a value must belong to a fact about an item the sentence names (pairing);
* when the sentence states a relation between items (connects, feeds, downstream of,
  operates), a fact computed by a tool must relate those items, in that direction.

Facts are never chained here: reachability counts only if ``traverse``/``find_path`` computed
it. A sentence without references is checked against all facts and can be at most "limited".
What cannot be established is reported, never assumed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pid_agent.agent.claims import (
    INSTRUMENT_PREDICATES,
    LIVE_STATE,
    PROMPT_LEAK_LENGTH,
    Fact,
    FactIndex,
    build_facts,
    key,
    name_tokens,
    render_claim,
    split_answer,
    validate_claim,
)
from pid_agent.agent.compact import _connection_line
from pid_agent.agent.grounding import (
    DISCLAIMER,
    GENERIC_PROPERTY_WORDS,
    PATTERNS,
    SENTENCE_SPLIT,
    TYPOGRAPHY,
    Claim,
    EvidenceCorpus,
    _role_problems,
    extract_claims,
    identifier_pieces,
)

REF = r"[ER]\d+(?:\.\d+)?"
CITATION = re.compile(rf"\[\s*({REF}(?:\s*[,;]\s*{REF})*)\s*\]")
# A bracket that looks like a citation but is not one: [E2], [E2.x], [R 3], [E2.1 - E2.4] ...
MALFORMED_CITATION = re.compile(r"\[\s*[ER]\s*[\d.][^\]]*\]|\[\s*(?:ref|evidence)[^\]]*\]", re.IGNORECASE)
TRAILING_CITATION = re.compile(rf"([.!?:;])(\s*)((?:\[\s*{REF}(?:\s*[,;]\s*{REF})*\s*\]\s*)+)")
# Words that state a relation between the items a sentence names.
DIRECT = re.compile(r"\b(?:directly|immediately|adjacent)\b", re.IGNORECASE)
SIDE = re.compile(r"\b(downstream|upstream)\s+(?:of|from)\b", re.IGNORECASE)
SIDE_REACH = 80  # characters after "downstream of" within which the reference item is named


@dataclass(frozen=True)
class Relation:
    """One canonical relation and the wordings that state it.

    ``check`` says how it is verified: "flow" (the item named first is upstream of the one
    named after it along the drawn piping), "fed_by" (the passive of flow), or "link" (an
    instrumentation fact with ``predicate`` from the first item to the second; "by" after the
    phrase reverses it: "operated by").
    """

    name: str
    check: str
    phrases: str
    predicate: str | None = None


# The relation vocabulary: what the validator recognises and how each wording is checked.
# Wordings are generic topology and instrumentation terms; anything else is only checked for
# the items and values it names.
RELATIONS: tuple[Relation, ...] = (
    Relation("feeds", "flow", r"feeds?|feeding|supplies|supplying|discharges?(?:\s+(?:in)?to)?|discharging|delivers?|delivering|"
             r"sends?\s+(?:the\s+)?(?:fluid|flow|product|medium)\s+(?:on\s+)?to|flows?\s+(?:in)?to|flowing\s+(?:in)?to"),
    Relation("fed_by", "fed_by", r"(?:fed|supplied)\s+(?:by|from)|receives?\s+(?:its\s+|the\s+)?(?:fluid|flow|feed|product|medium)\s+from"),
    Relation("operates", "link", r"operat\w*|actuat\w*|acts?\s+on|controls|controlling|controlled", "operates"),
    Relation("sends_signal_to", "link", r"sends?\s+(?:its\s+|a\s+|the\s+)?(?:signal|output)s?\s+to|signals?\s+to|transmits?\s+(?:\w+\s+)?to", "sends_signal_to"),
    Relation("measurement_input_to", "link", r"(?:sends?|passes|feeds?)\s+(?:its\s+|the\s+)?measurements?\s+to", "measurement_input_to"),
    Relation("senses_at", "link", r"senses?(?:\s+at)?|sensed\s+at|measures?\s+at|measuring\s+at|takes?\s+(?:its\s+|the\s+)?measurements?\s+at", "senses_at"),
)
RELATION_PHRASES = [(relation, re.compile(rf"\b(?:{relation.phrases})\b", re.IGNORECASE)) for relation in RELATIONS]
# Any wording that says two named items are related, checked as "the tool results relate them".
RELATION = re.compile(
    r"\b(?:connect\w*|link\w*|join\w*|attach\w*|fed|discharg\w*|supply|deliver\w*|flows?|flowing|leads?|leading|"
    r"routes?|routed|path|between|downstream|upstream|reach\w*)\b|→|->|" + "|".join(rf"\b(?:{r.phrases})\b" for r in RELATIONS),
    re.IGNORECASE,
)
# What a sentence does not assert. A negation covers the rest of its clause ("P4711 does not
# feed T4750", "... H1007, not T4750"); a clause that reports the user's words or an assumption
# is not asserted at all. A hedge such as "if" or "your" elsewhere in the sentence changes nothing.
CLAUSE_BREAK = re.compile(r"[,;:()]|\s(?:but|however|whereas|while|although|though)\s|\s[-–—]\s", re.IGNORECASE)
NEGATION = re.compile(r"n['’]t\b|\b(?:not|no|never|nor|neither|cannot|without|rather\s+than|instead\s+of)\b", re.IGNORECASE)
ATTRIBUTED = re.compile(
    r"\byou\s+(?:said|stated|mentioned|asked|wrote|assumed|suggested)\b|\byour\s+(?:assumption|premise|question|statement)\b|"
    r"\bassum\w*|\bhypothetical\w*|\bun(?:verified|confirmed)\b|\bdid\s+you\s+mean\b",
    re.IGNORECASE,
)
# A sentence about the plant: it names a kind of plant item or a role. Without an identifier,
# value or checked relation the validator cannot tie it to evidence.
PLANT_STATEMENT = re.compile(
    r"\b(?:pumps?|compressors?|exchangers?|tanks?|vessels?|columns?|reactors?|drums?|heaters?|coolers?|filters?|separators?|"
    r"valves?|lines?|pipes?|piping|nozzles?|chambers?|flanges?|tees?|reducers?|fittings?|connectors?|equipment|"
    r"instruments?|transmitters?|controllers?|sensors?|actuators?|loops?|signals?|"
    r"main|primary|principal|purpose|used\s+(?:for|to)|serves?|responsible|designed|intended|role|duty)\b",
    re.IGNORECASE,
)
CONNECTIVE = re.compile(r":\s*$|\b(?:listed|shown)\s+below\b|\bas\s+follows\b|\bthe\s+following\b", re.IGNORECASE)
MAX_FACTS_SHOWN = 12


def annotate_refs(result: dict[str, Any], step: int) -> dict[str, Any]:
    """Give every row of a full tool result a deterministic evidence id, in place.

    ``R<step>`` is the whole result, ``E<step>.<n>`` a row, ``E<step>.0`` the result's status
    facts (not found, ambiguous, no path, where a traversal ended). Ids are assigned by code in
    a fixed order and are stable within one agent run.
    """
    counter = 0

    def next_ref() -> str:
        nonlocal counter
        counter += 1
        return f"E{step}.{counter}"

    result["result_ref"] = f"R{step}"
    result["status_ref"] = f"E{step}.0"
    for section in ("entities", "connections", "paths"):
        for row in result.get(section) or []:
            row["ref"] = next_ref()
    for report in (result.get("properties") or {}).values():
        if isinstance(report, dict) and "found" in report:
            for item in report["found"]:
                item["ref"] = next_ref()
            if report.get("missing"):
                report["missing_ref"] = next_ref()
    for row in result.get("boundaries") or []:
        row["ref"] = next_ref()
    for row in result.get("derived") or []:
        row["ref"] = next_ref()
    return result


# --------------------------------------------------------------------------- facts as a small graph
def _route(fact: Fact) -> list[str]:
    return list(fact.qualifiers.get("entities") or []) if fact.predicate in ("reaches", "path") else []


def _fact_strings(fact: Fact) -> list[str]:
    out = [fact.value, fact.qualifiers.get("property")]
    for name, value in fact.qualifiers.items():
        if name not in ("entities", "scope"):
            out += value if isinstance(value, list) else [value]
    return [str(v) for v in out if v not in (None, "")]


class Scope:
    """A set of facts, queried the way a sentence needs: who is involved, what is carried, what relates."""

    def __init__(self, facts: list[Fact], index: FactIndex) -> None:
        self.facts = facts
        ends: dict[str, set[str]] = {}
        for fact in index.facts:  # which entities a connection id joins
            connection = fact.qualifiers.get("connection")
            if connection:
                ends.setdefault(connection, set()).update(x for x in (fact.subject, fact.object) if x)
        self._ends = ends
        self._corpora: dict[str, EvidenceCorpus] = {}
        self._downstream: set[tuple[str, str]] | None = None

    def involved(self, fact: Fact) -> set[str]:
        """Entities and objects a fact is about."""
        who = {fact.subject, fact.object, fact.qualifiers.get("owner"), fact.qualifiers.get("part_of"), *_route(fact)}
        who |= self._ends.get(fact.subject, set())
        return {w for w in who if w}

    def carries(self, fact: Fact, token: Claim) -> bool:
        corpus = self._corpora.get(fact.id)
        if corpus is None:
            corpus = self._corpora[fact.id] = EvidenceCorpus([{"evidence": [re.sub(r"[\[\]]", " ", s) for s in _fact_strings(fact)]}])
        return corpus.supports(token) or ("/" in token.text and all(key(part) in corpus.terms for part in token.text.split("/")))

    def carriers(self, token: Claim) -> list[Fact]:
        return [f for f in self.facts if self.carries(f, token)]

    def mentions(self, entity_id: str) -> list[Fact]:
        return [f for f in self.facts if entity_id in self.involved(f)]

    def downstream_pairs(self) -> set[tuple[str, str]]:
        """(a, b): the facts show b downstream of a.

        Routes computed by traverse/find_path count as they are. Individual pipes may be followed
        one after another under the same rule the traversal uses: a path that enters an item
        through one chamber does not leave through a different one.
        """
        if self._downstream is not None:
            return self._downstream
        pairs: set[tuple[str, str]] = set()
        pipes: dict[str, list[tuple[str, Any, Any]]] = {}
        for fact in self.facts:
            if fact.predicate == "flows_to":
                pipes.setdefault(fact.subject, []).append((fact.object, fact.qualifiers.get("from_chamber"), fact.qualifiers.get("to_chamber")))
            route, direction = _route(fact), fact.qualifiers.get("direction")
            if direction in ("downstream", "upstream"):
                for i, a in enumerate(route):
                    for b in route[i + 1 :]:
                        pairs.add((a, b) if direction == "downstream" else (b, a))
        for start in pipes:
            seen, todo = set(), [(start, None)]
            while todo:
                node, entered = todo.pop()
                for target, leaves, arrives in pipes.get(node, []):
                    if node != start and entered and leaves and entered != leaves:
                        continue  # another side of the same equipment
                    if (target, arrives) not in seen:
                        seen.add((target, arrives))
                        pairs.add((start, target))
                        todo.append((target, arrives))
        self._downstream = pairs
        return pairs

    def related_pairs(self, direct_only: bool = False) -> set[frozenset[str]]:
        pairs: set[frozenset[str]] = set()
        for fact in self.facts:
            if fact.object and (fact.predicate == "flows_to" or fact.predicate in INSTRUMENT_PREDICATES.values()):
                pairs.add(frozenset((fact.subject, fact.object)))
            for name in ("owner", "part_of"):
                if fact.qualifiers.get(name):
                    pairs.add(frozenset((fact.subject, fact.qualifiers[name])))
        if not direct_only:
            pairs |= {frozenset(pair) for pair in self.downstream_pairs()}
            for fact in self.facts:  # a route found with direction "any"/"both" still relates its items
                route = _route(fact)
                pairs |= {frozenset((a, b)) for i, a in enumerate(route) for b in route[i + 1 :]}
        return {p for p in pairs if len(p) == 2}

    def hubs(self) -> set[str]:
        """Where the cited traversals and paths started: an enumeration need not repeat it."""
        return {f.subject for f in self.facts if f.predicate in ("reaches", "path")}


def _connected(named: set[str], pairs: set[frozenset[str]], hubs: set[str]) -> bool:
    nodes = named | hubs
    seen, todo = set(), [next(iter(named))]
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        todo += [other for pair in pairs if node in pair for other in pair if other in nodes and other not in seen]
    return named <= seen


# --------------------------------------------------------------------------- one sentence
@dataclass
class SentenceResult:
    text: str
    refs: list[str] = field(default_factory=list)
    used: list[Fact] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    anchored: bool = False
    factual: bool = False
    checked: int = 0


def _note(claim: str, kind: str, reason: str, sentence: str) -> dict[str, Any]:
    return {"claim": claim, "kind": kind, "reason": reason, "sentence": sentence}


def _name(index: FactIndex, entity_id: str) -> str:
    names = sorted(index.names_of(entity_id) - {entity_id}, key=len)
    return f"{entity_id} ({names[0]})" if names else entity_id


def _positions(text: str, mentions: dict[str, str]) -> list[tuple[int, str]]:
    """(character position, entity id) for every mention of an entity in the sentence."""
    found = []
    for token, entity_id in mentions.items():
        found += [(m.start(), entity_id) for m in re.finditer(re.escape(token), text)]
    return sorted(found)


def _masked(text: str) -> str:
    """``text`` with every identifier, value and type name blanked out, same length.

    Relation words are then found in the prose only, never inside a name such as
    "ActuatingFunction-1" or "FlowInPipeOffPageConnector-1".
    """
    text = text.translate(TYPOGRAPHY)  # one character for one, so positions are kept
    for _, pattern in PATTERNS:
        text = pattern.sub(lambda m: "#" * len(m.group(0)), text)
    return text


def _asserted(text: str) -> str:
    """``text`` with what it does not assert blanked out ("~"), same length.

    A negation blanks the rest of its clause; a clause that reports the user's words or an
    assumption is blanked whole. Everything else is checked, whatever hedge words it contains.
    """
    chars, start = list(text), 0
    for end in [m.start() for m in CLAUSE_BREAK.finditer(text)] + [len(text)]:
        clause = text[start:end]
        negation = NEGATION.search(clause)
        cut = start if ATTRIBUTED.search(clause) else start + negation.start() if negation else end
        chars[cut:end] = "~" * (end - cut)
        start = end
    return "".join(chars)


def _relation_mentions(text: str) -> list[tuple[re.Match[str], Relation]]:
    """The relation phrases in ``text``, left to right; a longer phrase wins over one inside it."""
    found = sorted(((m, r) for r, pattern in RELATION_PHRASES for m in pattern.finditer(text)), key=lambda x: (x[0].start(), -len(x[0].group(0))))
    kept: list[tuple[re.Match[str], Relation]] = []
    for match, relation in found:
        if not kept or match.start() >= kept[-1][0].end():
            kept.append((match, relation))
    return kept


def _relation_checks(text: str, mentions: dict[str, str], cited: Scope, everything: Scope, index: FactIndex, has_refs: bool, out: SentenceResult) -> None:
    shown, text = text, _asserted(_masked(text))
    # Items named where the sentence asserts something; a negated "not T4750" names nothing.
    where = [(pos, e) for pos, e in _positions(shown, mentions) if text[pos] != "~"]
    named = {e for _, e in where}
    if len(named) < 2:
        return

    def judge(holds_cited: bool, holds_anywhere: bool, contradicted: bool, claim: str, missing: str) -> None:
        if holds_cited:
            return
        if contradicted:
            out.problems.append(_note(claim, "relationship", missing, shown))
        elif holds_anywhere and has_refs:
            out.gaps.append(_note(claim, "uncited_relationship", "the tool results support this, but not the evidence this sentence cites", shown))
        elif not holds_anywhere:
            out.problems.append(_note(claim, "relationship", missing, shown))

    phrases = _relation_mentions(text)
    linked = False
    for match, relation in phrases:
        if relation.check != "link":
            continue
        before = [e for pos, e in where if pos < match.start()]
        after = [e for pos, e in where if pos >= match.end() and e != (before[-1] if before else None)]
        if not before or not after:
            continue
        if re.match(r"\s*(?:by|from)\b", text[match.end() :]):  # "X is operated by Y"
            before, after = after[:1], before[-1:]
        actor, predicate, linked = before[-1], relation.predicate, True

        def holds(scope: Scope) -> bool:
            return any(f.predicate == predicate and f.subject == actor and f.object in after for f in scope.facts)

        reverse = any(f.predicate == predicate and f.object == actor and f.subject in after for f in everything.facts)
        judge(holds(cited), holds(everything), reverse, f"{_name(index, actor)} {relation.name.replace('_', ' ')} {', '.join(_name(index, e) for e in after)}",
              "the link runs the other way in the tool results" if reverse else f"no tool result shows a '{relation.name.replace('_', ' ')}' link between these items")  # fmt: skip
    if linked:
        return  # instrumentation links are not piping; the flow checks below do not apply

    for match in SIDE.finditer(text):
        side = match.group(1).lower()
        reference = next((e for pos, e in where if match.end() <= pos <= match.end() + SIDE_REACH), None)
        if reference is None:
            out.gaps.append(_note(match.group(0), "unclear_relationship", "name the item right after 'downstream of' / 'upstream of' so the direction can be checked", shown))
            continue
        for other in sorted(named - {reference}):
            wanted = (reference, other) if side == "downstream" else (other, reference)
            opposite = (wanted[1], wanted[0])
            cited_pairs, all_pairs = cited.downstream_pairs(), everything.downstream_pairs()
            contradicted = wanted not in all_pairs and opposite in all_pairs
            judge(wanted in cited_pairs, wanted in all_pairs, contradicted, f"{_name(index, other)} {side} of {_name(index, reference)}",
                  f"the tool results show it {'upstream' if side == 'downstream' else 'downstream'}, not {side}" if contradicted else f"no tool result shows it {side} of that item")  # fmt: skip

    for match, relation in phrases:
        if relation.check not in ("flow", "fed_by"):
            continue
        before = [e for pos, e in where if pos < match.start()]
        after = [e for pos, e in where if pos >= match.end()]
        if not before or not after:
            if not SIDE.search(text):
                out.gaps.append(_note(match.group(0), "unclear_relationship", "write it as '<item> feeds <item>' so the direction can be checked", shown))
            continue
        # The subject is one of the items named before the verb (after it, in the passive).
        sources, targets = (before, after) if relation.check == "flow" else (after[:1], before[-1:])
        cited_pairs, all_pairs = cited.downstream_pairs(), everything.downstream_pairs()
        for target in sorted(set(targets) - set(sources)):
            contradicted = not any((s, target) in all_pairs for s in sources) and all((target, s) in all_pairs for s in sources)
            judge(any((s, target) in cited_pairs for s in sources), any((s, target) in all_pairs for s in sources), contradicted,
                  f"{_name(index, sources[-1])} feeds {_name(index, target)}",
                  "the tool results show the opposite flow direction" if contradicted else "no tool result shows piping from the first item to the second")  # fmt: skip

    if RELATION.search(text):
        direct = bool(DIRECT.search(text))
        ok_cited = _connected(named, cited.related_pairs(direct), set() if direct else cited.hubs())
        ok_all = _connected(named, everything.related_pairs(direct), set() if direct else everything.hubs())
        judge(ok_cited, ok_all, False, " / ".join(sorted(_name(index, e) for e in named)),
              "no tool result shows a direct connection between these items" if direct else "no tool result relates these items to each other")  # fmt: skip


def _property_words(name: str) -> set[str]:
    return {w for w in name_tokens(name) if w not in GENERIC_PROPERTY_WORDS}


def _misattributed(token: Claim, carriers: list[Fact], everything: Scope, text: str) -> str | None:
    """A measured value described with the name of a different property than the one that carries it."""
    if token.kind != "value_with_unit":
        return None
    own = {str(f.qualifiers["property"]) for f in carriers if f.qualifiers.get("property")}
    if not own:
        return None
    words, squeezed = set(re.findall(r"[a-z]+", text.lower())), key(text)
    if any(key(name) in squeezed or (_property_words(name) and _property_words(name) <= words) for name in own):
        return None
    others = {str(f.qualifiers["property"]) for f in everything.facts if f.predicate == "has_property" and f.qualifiers.get("property")} - own
    named = sorted(name for name in others if _property_words(name) and _property_words(name) <= words)
    if not named:
        return None
    return f"this value belongs to {', '.join(sorted(own))} in the tool results, but the sentence describes {', '.join(named)}"


def _written_identifier_owner(token: Claim, text: str, cited: Scope, everything: Scope) -> str | None:
    """The item whose complete identifier the sentence writes out and ``token`` is only part of.

    "K 2750" is read as the tokens "K" and "2750"; the number is then not a value of its own but
    the tag of one item. The cited facts must give that identifier to the item, and no tool
    result may give it to any other item.
    """
    text = text.translate(TYPOGRAPHY)
    written = set()
    for fact in cited.facts:
        value = str(fact.value or "")
        if fact.predicate != "identified_as" or key(value) == token.key or token.key not in identifier_pieces(value):
            continue
        spelled = r"\s*".join(re.escape(c) for c in re.sub(r"\s+", "", value))
        if re.search(rf"(?<!\w){spelled}(?!\w)", text, re.IGNORECASE):
            written.add(key(value))
    owners = {f.subject for f in everything.facts if f.predicate == "identified_as" and key(f.value) in written}
    return owners.pop() if len(owners) == 1 else None


def check_sentence(sentence: str, index: FactIndex, extra: list[Fact], corpus: EvidenceCorpus, question_terms: set[str]) -> SentenceResult:
    refs: list[str] = []
    for match in CITATION.finditer(sentence):
        refs += [r for r in re.split(r"\s*[,;]\s*", match.group(1)) if r not in refs]
    text = CITATION.sub(" ", sentence).strip()
    out = SentenceResult(text=text, refs=refs)

    for match in MALFORMED_CITATION.finditer(text):
        out.problems.append(_note(match.group(0), "bad_reference", "not a valid evidence reference; use ids exactly as the tool results give them", text))
    text = MALFORMED_CITATION.sub(" ", text)
    known = index.known_refs()
    for ref in refs:
        if ref not in known:
            out.problems.append(_note(ref, "bad_reference", "no tool result has an evidence row with this id", text))
    cited_facts = [f for ref in refs if ref in known for f in index.by_ref(ref)] + extra
    has_refs = bool(refs) or bool(extra)
    everything = Scope(index.facts, index)
    cited = Scope(cited_facts, index) if has_refs else everything

    tokens = []
    for token in extract_claims(text):
        if all(t.key != token.key for t in tokens):
            tokens.append(token)
    if not tokens:
        # Nothing here can be tied to evidence. A statement about the plant ("It is the main
        # cooling water pump") is then unchecked, and the answer can be at most limited.
        if PLANT_STATEMENT.search(_asserted(text.translate(TYPOGRAPHY))) and not CONNECTIVE.search(text):
            out.factual, out.checked = True, 1
            out.gaps.append(_note(text[:80], "unchecked_statement", "a statement about the plant with no identifier, value or relation the validator can check against the evidence", text))
        return out
    out.factual, out.checked = True, len(tokens)

    mentions: dict[str, str] = {}  # token text -> entity id
    values: list[Claim] = []
    shared: list[tuple[Claim, list[str]]] = []  # identifiers that several entities carry
    for token in tokens:
        ids, how = index.resolve(token.text)
        whole = _written_identifier_owner(token, text, cited, everything)
        if how in ("entity", "object"):
            mentions[token.text] = ids[0]
        elif whole:
            mentions[token.text] = whole  # "2750" of "K 2750": the sentence names the item, not a value
        elif how == "ambiguous":
            if not any(f.predicate == "ambiguous" and key(f.value) == token.key for f in cited.facts):
                shared.append((token, ids))
        else:
            owners = {f.subject for f in everything.carriers(token)}
            if len(owners) == 1 and all(f.predicate == "identified_as" for f in everything.carriers(token)):
                mentions[token.text] = owners.pop()  # part of one item's identifier, e.g. "SV 104.01"
            else:
                values.append(token)
    named = set(mentions.values())

    for token, ids in shared:
        # A shared identifier (a loop number on every instrument of the loop) may be stated about
        # the items the sentence names, when the cited facts give it to those very items.
        backing = [f for f in cited.carriers(token) if f.subject in named & set(ids)]
        if backing:
            out.used += backing[:2]
            out.anchored = True
        else:
            out.problems.append(_note(token.text, "ambiguous_identifier", f"matches several entities ({', '.join(ids)}); the graph selected none", text))

    for token_text, entity_id in mentions.items():
        facts = cited.mentions(entity_id)
        if facts:
            out.used += facts[:2]
            out.anchored = True
        else:
            out.gaps.append(_note(token_text, "uncited", "this item is in the tool results, but not in the evidence this sentence cites", text))

    for token in values:
        carriers = cited.carriers(token)
        paired = [f for f in carriers if not named or cited.involved(f) & named]
        if paired:
            wrong = _misattributed(token, paired, everything, text)
            if wrong:
                out.problems.append(_note(token.text, "value_attribution", wrong, text))
                continue
            out.used += paired[:2]
            out.anchored = True
            continue
        elsewhere = [f for f in everything.carriers(token) if not named or everything.involved(f) & named]
        if elsewhere and has_refs:
            out.gaps.append(_note(token.text, "uncited", "supported by a tool result that this sentence does not cite", text))
            out.anchored = True
        elif carriers or everything.carriers(token):
            owners = sorted({_name(index, f.subject) for f in (carriers or everything.carriers(token))})[:3]
            out.problems.append(_note(token.text, "pairing", f"in the tool results this value belongs to {', '.join(owners)}, not to {', '.join(sorted(_name(index, e) for e in named))}", text))
        elif corpus.supports(token) or ("/" in token.text and all(key(p) in corpus.terms for p in token.text.split("/"))):
            # Present in a tool result but not as a graph fact, for example a near-miss
            # suggestion. It may be offered as a possibility, never stated as a fact.
            if DISCLAIMER.search(text):
                out.gaps.append(_note(token.text, "untyped", "found in the tool results only as a suggestion or note, not as a graph fact", text))
                out.anchored = True
            else:
                out.problems.append(_note(token.text, "untyped", "the tool results mention this only as a suggestion or note; it is not an established graph fact", text))
        elif token.key in question_terms and DISCLAIMER.search(text):
            out.anchored = True  # the user's own term, reported as not found / not confirmed
        else:
            reason = "appears only in the question and is stated as if it were a graph fact" if token.key in question_terms else "not found in any tool result"
            out.problems.append(_note(token.text, token.kind, reason, text))

    _relation_checks(text, mentions, cited, everything, index, has_refs, out)
    if not has_refs and not out.problems and (mentions or any(g["kind"] == "untyped" for g in out.gaps) or out.used):
        out.gaps.append(_note(text[:80], "unreferenced", "states plant facts without an evidence reference", text))
    return out


# --------------------------------------------------------------------------- the whole answer
@dataclass
class ClaimReport:
    answer: str = ""
    has_claims: bool = False  # the answer carried evidence references or a claims block
    supported: list[dict[str, Any]] = field(default_factory=list)    # statement, refs, facts
    rejected: list[dict[str, Any]] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)     # must not reach the user
    gaps: list[dict[str, Any]] = field(default_factory=list)         # shown only as "limited"
    checked: int = 0
    anchored: bool = False  # the answer rests on at least one graph-derived statement
    ambiguous: bool = False

    @property
    def level(self) -> str:
        if self.problems or not self.anchored:
            return "insufficient_evidence"
        if self.gaps:
            return "limited"
        return "ambiguous" if self.ambiguous else "grounded"


def _quotes(text: str, protected: str) -> bool:
    squeezed, source = re.sub(r"\s+", " ", text), re.sub(r"\s+", " ", protected)
    return any(source[i : i + PROMPT_LEAK_LENGTH] in squeezed for i in range(0, max(len(source) - PROMPT_LEAK_LENGTH, 0), PROMPT_LEAK_LENGTH // 2))


def sentences_of(prose: str) -> list[str]:
    """Sentences and list items, with a citation written after the full stop kept with its sentence."""
    text = TRAILING_CITATION.sub(lambda m: f" {m.group(3).strip()}{m.group(1)}{m.group(2)}", prose.translate(TYPOGRAPHY))
    out: list[str] = []
    for sentence in (s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()):
        if out and out[-1].rstrip().endswith(":") and not CITATION.search(out[-1]) and CITATION.search(sentence):
            # A lead-in line ("The valves are:") is covered by the evidence of the item below it.
            out[-1] = f"{out[-1]} {' '.join(m.group(0) for m in CITATION.finditer(sentence))}"
        if CITATION.search(sentence) and not CITATION.sub("", sentence).strip(" .:;-*"):
            # A citation on a line of its own covers the uncited lines directly above it
            # (a list followed by its reference).
            position = len(out) - 1
            while position >= 0 and not CITATION.search(out[position]):
                out[position] = f"{out[position]} {sentence}"
                position -= 1
            if position == len(out) - 1:
                out.append(sentence)  # nothing above to attach to
        else:
            out.append(sentence)
    return out


# ------------------------------------------------------------------ answers rendered by the application
def _row_text(row: dict[str, Any], section: str, result: dict[str, Any]) -> str:
    if section == "connections":
        return _connection_line(row)
    if section == "paths":
        text = "Route: " + " -> ".join(f"{e['name']} ({e['id']})" for e in row["entities"]) + f"; {row['length']} pipe(s), direction {row['direction']}"
        return text + (f" (with {', '.join(row['blocked'])} treated as closed)" if row.get("blocked") else "")
    if section == "boundaries":
        return f"Chamber boundary at {row['equipment']}: entered through {row['entered_chamber']}, not continued into {row['blocked_chamber']}"
    text = f"{row['name']} ({row['id']}), {row['type']}"
    if row.get("attributes"):
        text += ": " + ", ".join(f"{a['property']} = {a['value']}" + (f" (on {a['on']})" if a.get("on") else "") for a in row["attributes"])
    if "distance" in row:
        direction = (result.get("input") or {}).get("direction", "downstream")
        text += f": {direction} of {row['path_entities'][0]}, {row['distance']} pipe(s) away"
        if row.get("through_equipment"):
            text += f", through {', '.join(row['through_equipment'])}"
        text += ", end of drawn piping" if row.get("terminal") else (", piping continues beyond the search depth" if row.get("continues_beyond_max_depth") else "")
        blocked = (result.get("meta") or {}).get("blocked")
        if blocked:
            text += f" (with {', '.join(blocked)} treated as closed)"
    return text


def _status_text(result: dict[str, Any]) -> list[str]:
    lines = [str(result["message"])] if result.get("status") in ("not_found", "ambiguous", "empty") and result.get("message") else []
    for end in (result.get("meta") or {}).get("endpoint_details") or []:
        lines.append(f"{end['name']} ({end['id']}): " + ("the piping leaves this drawing here; its destination is not shown" if end["kind"] == "drawing_end" else "end of drawn piping"))
    return lines


def render_rows(refs: list[str], observations: list[dict[str, Any]]) -> list[tuple[str, str]] | None:
    """(text, ref) for each cited evidence row, written by code from the structured result.

    R<step> stands for the rows that answer that tool's question (reached entities for a
    traversal, connections for an adjacency lookup, and so on). None if a ref is unknown.
    """
    by_step = {int(r["result_ref"][1:]): r for r in observations if r.get("result_ref")}
    rows: dict[str, list[str]] = {}
    for step, result in by_step.items():
        main = "connections" if result["tool"] in ("get_connections", "trace_instrumentation", "trace_line") else "paths" if result.get("paths") else "entities"
        if result.get("derived") and result["tool"] == "isolation_boundary":
            main = "derived"  # the item itself is context, not a finding
        whole: list[str] = []
        for section in ("entities", "connections", "paths", "boundaries"):
            for row in result.get(section) or []:
                rows[row["ref"]] = [_row_text(row, section, result)]
                if section in (main, "boundaries"):
                    whole.append(row["ref"])
        for object_id, report in (result.get("properties") or {}).items():
            if isinstance(report, dict) and "found" in report:
                for item in report["found"]:
                    rows[item["ref"]] = [f"{item['source_object_id']}: {item['property']} = {item['value']}"]
                    whole.append(item["ref"])
                if report.get("missing_ref"):
                    rows[report["missing_ref"]] = [f"{object_id}: not present in the P&ID: {', '.join(report['missing'])}"]
                    whole.append(report["missing_ref"])
        for row in result.get("derived") or []:
            rows[row["ref"]] = [row["statement"]]
            whole.append(row["ref"])
        status = _status_text(result)
        if status:
            rows[f"E{step}.0"] = status
            whole.append(f"E{step}.0")
        rows[f"R{step}"] = whole  # type: ignore[assignment]
    out: list[tuple[str, str]] = []
    for ref in refs:
        if ref not in rows:
            return None
        for item in rows[ref] if ref.startswith("R") else [ref]:
            out += [(text, item) for text in rows[item]] if ref.startswith("R") else [(text, ref) for text in rows[ref]]
    return out


def check_answer(draft: str, question: str, observations: list[dict[str, Any]], protected_text: str = "") -> ClaimReport:
    """Validate one drafted answer against the tool results. Deterministic; no model call."""
    prose, claims = split_answer(draft)
    index = build_facts(observations)
    cited_only = [r for m in CITATION.finditer(prose) for r in re.split(r"\s*[,;]\s*", m.group(1))]
    if cited_only and not CITATION.sub("", prose).strip(" .:;-*\n") and claims is None:
        # The model answered with evidence ids alone: the application writes the rows out.
        rendered = render_rows(list(dict.fromkeys(cited_only)), observations)
        if rendered:
            report = ClaimReport(answer="\n".join(f"- {text} [{ref}]" for text, ref in rendered), has_claims=True, anchored=True, checked=len(rendered))
            for text, ref in rendered:
                report.supported.append({"claim": {"predicate": "rendered", "refs": [ref]}, "text": f"{text} [{ref}]", "refs": [ref], "facts": [f.to_dict() for f in index.by_ref(ref)[:MAX_FACTS_SHOWN]]})
            report.ambiguous = any(f.predicate == "ambiguous" for _, ref in rendered for f in index.by_ref(ref))
            return report
    corpus = EvidenceCorpus(observations)
    question_terms = {c.key for c in extract_claims(question)}
    report = ClaimReport(answer=prose, has_claims=claims is not None or bool(CITATION.search(prose)))

    # Typed claims remain accepted: each must be entailed by a fact, and the facts that entail
    # them count as cited evidence for the text.
    extra: list[Fact] = []
    for claim in claims or []:
        report.checked += 1
        ok, reason, facts = validate_claim(claim, index)
        if ok:
            extra += facts
            report.supported.append({"claim": claim, "text": render_claim(claim), "facts": [f.to_dict() for f in facts]})
            report.ambiguous = report.ambiguous or claim.get("predicate") == "ambiguous"
        else:
            report.rejected.append({"claim": claim, "text": render_claim(claim), "reason": reason})
            report.problems.append({"claim": render_claim(claim), "kind": "structured_claim", "reason": reason})
    named_by_claims = [f for c in claims or [] if isinstance(c, dict) for name in ("subject", "object") if c.get(name) for e in index.resolve(c[name])[0] for f in index.facts if f.subject == e and f.predicate in ("is_a", "identified_as")]
    extra += named_by_claims if extra else []

    for sentence in sentences_of(prose):
        result = check_sentence(sentence, index, extra, corpus, question_terms)
        report.checked += result.checked
        report.problems += result.problems
        report.gaps += result.gaps
        report.anchored = report.anchored or result.anchored
        if result.refs and result.factual and not result.problems:
            facts, seen = [], set()
            for fact in result.used:
                if fact.id not in seen and len(facts) < MAX_FACTS_SHOWN:
                    seen.add(fact.id)
                    facts.append(fact.to_dict())
            report.supported.append({"claim": {"predicate": "cited", "refs": result.refs}, "text": f"{result.text} [{', '.join(result.refs)}]", "refs": result.refs, "facts": facts})
            report.ambiguous = report.ambiguous or any(f.predicate == "ambiguous" for ref in result.refs for f in index.by_ref(ref) if ref in index.known_refs())
        match = LIVE_STATE.search(result.text)
        if match and not DISCLAIMER.search(result.text):
            report.problems.append(_note(match.group(0), "operating_state", "a P&ID does not contain current operating state; topology does not show what is open, running or flowing now", result.text))

    scope_keys = {key(s) for item in report.supported for f in item["facts"] for s in (f.get("value"), *(f.get("qualifiers") or {}).values()) if isinstance(s, str)}
    report.problems += [p for p in _role_problems(CITATION.sub(" ", prose), corpus) if key(p["claim"].split(" ", 1)[1]) not in scope_keys]
    if protected_text and _quotes(prose, protected_text):
        report.problems.append({"claim": "(instructions)", "kind": "prompt_disclosure", "reason": "the answer reproduces the agent's instructions"})
    if not report.has_claims and not report.problems:
        report.gaps.append({"claim": "(no evidence references)", "kind": "missing_claims", "reason": "the answer cited no evidence, so it was checked against all tool results and is at most limited"})
    report.anchored = report.anchored or bool(report.supported)
    return report
