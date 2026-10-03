"""Relation grounding after the post-evaluation hardening. No model, no network.

* A hedge word ("if", "your") does not switch relation checking off for the sentence; only a
  negation (for the rest of its clause) or a clause that reports the user's words is exempt.
* Relations are recognised from a small vocabulary of generic wordings, each mapped to one
  canonical relation and checked in its direction.
* A statement about the plant with nothing checkable in it is never "grounded".
"""

from __future__ import annotations

import pytest

from pid_agent.agent.evidence_refs import RELATIONS, check_answer
from test_evidence_refs import P4711, observe, ref_of


def verdict(text, obs):
    report = check_answer(text, "q", obs)
    return report.level, {p["kind"] for p in report.problems}, {g["kind"] for g in report.gaps}


@pytest.fixture()
def pipe(tools):
    """P4711 -> H1007 through line 47122: the row citing it."""
    obs = observe(tools, P4711)
    return obs, ref_of(obs[0], "connections", id="PlateHeatExchanger-1")


# ================================================================== 1. hedges do not disable checks
def test_hedged_sentence_is_still_checked_for_direction(pipe):
    obs, row = pipe
    level, problems, _ = verdict(f"If you follow the piping, H1007 feeds P4711. [{row}]", obs)
    assert level == "insufficient_evidence" and "relationship" in problems
    assert verdict(f"If you follow the piping, P4711 feeds H1007. [{row}]", obs)[0] == "grounded"
    level, problems, _ = verdict(f"H1007 feeds P4711, as your drawing shows. [{row}]", obs)
    assert level == "insufficient_evidence" and "relationship" in problems


@pytest.mark.parametrize(
    "text",
    [
        "P4711 does not feed T4750. [{row}]",  # a negated relation is not asserted
        "P4711 doesn't feed T4750. [{row}]",
        "P4711 feeds H1007, not T4750. [{row}]",  # the negated item is not an operand
        "You said T4750 feeds P4711, but P4711 feeds H1007. [{row}]",  # the user's words are reported, not asserted
        "No tool result shows that T4750 feeds P4711. [{row}]",
    ],
)
def test_negations_and_reported_assumptions_are_not_asserted(pipe, text):
    obs, row = pipe
    assert "relationship" not in verdict(text.format(row=row), obs)[1], text


def test_a_negation_covers_only_its_own_clause(pipe):
    obs, row = pipe
    level, problems, _ = verdict(f"There is no bypass, and H1007 feeds P4711. [{row}]", obs)
    assert level == "insufficient_evidence" and "relationship" in problems


# ================================================================== 2. relation vocabulary
FLOW_WORDINGS = [
    ("{a} feeds {b}.", "{b} feeds {a}."),
    ("{a} supplies {b}.", "{b} supplies {a}."),
    ("{a} discharges to {b}.", "{b} discharges to {a}."),
    ("{a} sends fluid to {b}.", "{b} sends fluid to {a}."),
    ("Fluid from {a} flows to {b}.", "Fluid from {b} flows to {a}."),
    ("{b} is fed by {a}.", "{a} is fed by {b}."),
    ("{b} is supplied by {a}.", "{a} is supplied by {b}."),
    ("{b} receives fluid from {a}.", "{a} receives fluid from {b}."),
    ("{b} is downstream of {a}.", "{a} is downstream of {b}."),
    ("{a} is upstream of {b}.", "{b} is upstream of {a}."),
]


@pytest.mark.parametrize(("right", "reversed_"), FLOW_WORDINGS)
def test_flow_wordings_are_checked_in_their_direction(pipe, right, reversed_):
    obs, row = pipe
    assert verdict(right.format(a="P4711", b="H1007") + f" [{row}]", obs)[0] == "grounded", right
    level, problems, _ = verdict(reversed_.format(a="P4711", b="H1007") + f" [{row}]", obs)
    assert level == "insufficient_evidence" and "relationship" in problems, reversed_


def test_connected_to_needs_a_connection(pipe, tools):
    obs, row = pipe
    assert verdict(f"P4711 is connected to H1007. [{row}]", obs)[0] == "grounded"
    obs = observe(tools, P4711, ("find_entities", {"query": "T4750"}))
    level, problems, _ = verdict("P4711 is connected to T4750. [R1, R2]", obs)
    assert level == "insufficient_evidence" and "relationship" in problems


@pytest.fixture()
def actuator(tools):
    """HV4750.01 (ActuatingFunction-2) operates GlobeValve-2."""
    obs = observe(tools, ("get_connections", {"entity_id": "ActuatingFunction-2", "relationship": "instrumentation"}))
    return obs, ref_of(obs[0], "connections", id="GlobeValve-2")


@pytest.mark.parametrize("verb", ["operates", "actuates", "controls", "acts on"])
def test_operate_wordings_are_checked_in_their_direction(actuator, verb):
    obs, row = actuator
    assert verdict(f"HV4750.01 {verb} GlobeValve-2. [{row}]", obs)[0] == "grounded"
    level, problems, _ = verdict(f"GlobeValve-2 {verb} HV4750.01. [{row}]", obs)
    assert level == "insufficient_evidence" and "relationship" in problems


def test_passive_operate_and_the_noun_control(actuator):
    obs, row = actuator
    assert verdict(f"GlobeValve-2 is controlled by HV4750.01. [{row}]", obs)[0] == "grounded"
    assert verdict(f"HV4750.01 is controlled by GlobeValve-2. [{row}]", obs)[0] == "insufficient_evidence"
    # "control" as a noun states no relation
    assert "relationship" not in verdict(f"The control function HV4750.01 and GlobeValve-2 appear together. [{row}]", obs)[1]


def test_sensing_and_signal_wordings(tools):
    obs = observe(tools, ("get_connections", {"entity_id": "ProcessSignalGeneratingFunction-2", "relationship": "instrumentation"}),
                  ("get_connections", {"entity_id": "ProcessInstrumentationFunction-2", "relationship": "instrumentation"}))  # fmt: skip
    sensing = ref_of(obs[0], "connections", id="BlindFlange-2")
    signal = ref_of(obs[1], "connections", id="ActuatingFunction-1")
    for verb in ("senses at", "measures at", "takes its measurement at"):
        assert verdict(f"PT4712.02 {verb} BlindFlange-2. [{sensing}]", obs)[0] == "grounded", verb
        assert verdict(f"BlindFlange-2 {verb} PT4712.02. [{sensing}]", obs)[0] == "insufficient_evidence", verb
    assert verdict(f"PICSA4712.02 sends its signal to ActuatingFunction-1. [{signal}]", obs)[0] == "grounded"
    assert verdict(f"ActuatingFunction-1 sends its signal to PICSA4712.02. [{signal}]", obs)[0] == "insufficient_evidence"


def test_vocabulary_is_data_with_one_check_per_relation():
    assert {r.check for r in RELATIONS} == {"flow", "fed_by", "link"}
    assert all(r.predicate for r in RELATIONS if r.check == "link")
    names = [r.name for r in RELATIONS]
    assert len(names) == len(set(names))


# ================================================================== 3. statements with nothing checkable
@pytest.mark.parametrize(
    "extra",
    [
        "It is the main cooling water pump.",  # invented purpose
        "This valve serves as the emergency isolation valve.",  # unsupported role
        "The pump feeds the heat exchanger.",  # a relation between items that are not named
    ],
)
def test_unchecked_plant_statement_is_at_most_limited(pipe, extra):
    obs, row = pipe
    level, problems, gaps = verdict(f"P4711 feeds H1007. [{row}] {extra}", obs)
    assert level == "limited" and "unchecked_statement" in gaps and not problems, extra


@pytest.mark.parametrize(
    "extra",
    [
        "Here is what the graph shows.",
        "The connections are listed below:",
        "In short, see the evidence above.",
        "The P&ID does not contain a weight for this pump.",  # an absence, not an assertion
    ],
)
def test_connective_prose_and_absences_keep_the_answer_grounded(pipe, extra):
    obs, row = pipe
    assert verdict(f"{extra} P4711 feeds H1007. [{row}]", obs)[0] == "grounded", extra


def test_evidence_supported_statement_is_grounded(pipe):
    obs, row = pipe
    assert verdict(f"P4711 is connected to H1007 through line 47122, DN 80. [{row}]", obs)[0] == "grounded"
