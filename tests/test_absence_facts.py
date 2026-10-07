"""What an empty traversal may be cited for.

No model, no network. "Nothing was reached" is a fact only with its conditions: where the
search started, in which direction, with what treated as closed, for which types, and whether
it ran to the end of the drawn piping or was cut off.
"""

from __future__ import annotations

from fakes import ScriptedLLM, call
from pid_agent.agent.answer import EvidenceRegistry, absence_is_definitive, validate_submission
from pid_agent.agent.evidence_refs import annotate_refs
from pid_agent.agent.status import Provenance
from pid_agent.agent.workflow import PidAgent

TANK, PUMP, VALVE = "Tank-1", "CentrifugalPump-1", "BallValve-1"
NAMES: dict[str, str] = {}  # the names that exist in the graph: what a status row may show
SHUT = {"start_entity_id": "T4750", "direction": "downstream", "entity_types": ["equipment"], "blocked_entity_ids": [VALVE]}


def traverse(tools, **arguments):
    NAMES.update(tools.graph_names())
    return [annotate_refs(tools.call("traverse", arguments).to_dict(), 1)]


def absence(obs):
    """(the absence fact of an empty traversal, the wording of its status row)."""
    registry = EvidenceRegistry(obs, Provenance("", NAMES))
    facts = [f for f in registry.facts("E1.0") if f["p"] in ("reaches_nothing", "found_nothing_within_search_limits")]
    assert len(facts) == 1
    return facts[0], registry.rows("E1.0")[0][0]


def test_a_completed_empty_traversal_with_a_type_filter_states_the_filter(tools):
    obs = traverse(tools, **SHUT)
    fact, text = absence(obs)
    assert obs[0]["status"] == "empty" and absence_is_definitive(obs[0])
    assert fact == {"p": "reaches_nothing", "s": TANK, "q": {"direction": "downstream", "blocked": [VALVE], "semantics": "drawn_flow", "entity_types": ["equipment"], "max_depth": 25, "complete": True}}
    assert text == f"Nothing of type equipment is downstream of {TANK} with {VALVE} treated as closed. The search covered all the drawn piping in that direction."


def test_a_completed_empty_traversal_without_a_filter_is_about_everything_and_says_so(tools):
    fact, text = absence(traverse(tools, start_entity_id="BlindFlange-1", direction="downstream"))
    assert fact["p"] == "reaches_nothing" and "entity_types" not in fact["q"] and fact["q"]["complete"] is True
    assert text == "Nothing at all is downstream of BlindFlange-1. The search covered all the drawn piping in that direction (no type filter)."
    assert "equipment" not in text


def test_a_truncated_empty_traversal_is_not_an_absence(tools):
    obs = traverse(tools, start_entity_id="T4750", direction="downstream", entity_types=["equipment"], max_depth=2)
    fact, text = absence(obs)
    assert obs[0]["status"] == "empty" and obs[0]["meta"]["truncated_by_max_depth"] and not absence_is_definitive(obs[0])
    assert fact["p"] == "found_nothing_within_search_limits" and fact["q"]["complete"] is False and fact["q"]["max_depth"] == 2
    assert "within 2 pipe(s)" in text and "does not show that nothing lies beyond" in text
    assert "reaches_nothing" not in [f["p"] for f in EvidenceRegistry(obs).all_facts()]
    # the same search without the limit does find equipment: the bounded result proved nothing
    assert tools.call("traverse", {"start_entity_id": "T4750", "direction": "downstream", "entity_types": ["equipment"]}).to_dict()["status"] == "success"


def test_a_filter_the_graph_does_not_know_or_a_stop_condition_is_not_an_absence_either(tools):
    unknown, _ = absence(traverse(tools, start_entity_id="T4750", direction="downstream", entity_types=["reactors"]))
    assert unknown["p"] == "found_nothing_within_search_limits" and unknown["q"]["unknown_types"] == ["reactors"] and "entity_types" not in unknown["q"]
    stopped = traverse(tools, start_entity_id="T4750", direction="downstream", entity_types=["heat exchanger"], stop_at_types=["valve"])
    if stopped[0]["status"] == "empty":
        fact, text = absence(stopped)
        assert fact["p"] == "found_nothing_within_search_limits" and "the search was limited" in text


def test_the_items_treated_as_closed_are_part_of_the_fact(tools):
    shut, _ = absence(traverse(tools, **SHUT))
    assert shut["q"]["blocked"] == [VALVE]
    open_ = traverse(tools, **{k: v for k, v in SHUT.items() if k != "blocked_entity_ids"})
    assert open_[0]["status"] == "success"  # with the valve open there is equipment downstream
    assert "reaches_nothing" not in [f["p"] for f in EvidenceRegistry(open_).all_facts()]


def test_the_direction_is_part_of_the_fact(tools):
    fact, text = absence(traverse(tools, start_entity_id="P4711", direction="upstream", entity_types=["equipment"]))
    assert fact["q"]["direction"] == "upstream" and fact["s"] == PUMP and f"is upstream of {PUMP}" in text
    other, _ = absence(traverse(tools, start_entity_id="BlindFlange-1", direction="downstream", entity_types=["equipment"]))
    assert other["q"]["direction"] == "downstream" and other != fact


def test_piping_that_leaves_the_drawing_is_named_with_the_absence(tools):
    # Downstream of this tee the piping ends at an off-page connector: nothing of the type is on this drawing, and the answer says where the drawing ends.
    obs = traverse(tools, start_entity_id="PipeTee-5", direction="downstream", entity_types=["equipment"])
    fact, text = absence(obs)
    assert fact["p"] == "reaches_nothing" and fact["q"]["leaves_drawing_at"] == ["FlowOutPipeOffPageConnector-1"]
    assert text.endswith("The piping leaves this drawing at FlowOutPipeOffPageConnector-1; what is connected beyond is not shown.")
    closed, text = absence(traverse(tools, start_entity_id="BlindFlange-1", direction="downstream"))
    assert "leaves_drawing_at" not in closed["q"] and "leaves this drawing" not in text


def test_the_same_start_with_different_filters_gives_distinct_facts(tools):
    from pid_agent.agent.answer import fact_key

    start = {"start_entity_id": "BlindFlange-1", "direction": "downstream"}
    plain, _ = absence(traverse(tools, **start))
    equipment, _ = absence(traverse(tools, **start, entity_types=["equipment"]))
    valves, _ = absence(traverse(tools, **start, entity_types=["valve"]))
    bounded, _ = absence(traverse(tools, **start, entity_types=["equipment"], max_depth=3))
    assert len({fact_key(f) for f in (plain, equipment, valves, bounded)}) == 4
    assert equipment["q"]["entity_types"] == ["equipment"] and valves["q"]["entity_types"] == ["valve"] and bounded["q"]["max_depth"] == 3


def test_an_unfiltered_traversal_that_lists_no_equipment_is_not_cited_as_no_equipment(tools):
    # Rows are returned, none of them equipment. Citing them states those rows and nothing more.
    obs = traverse(tools, start_entity_id="BallValve-3", direction="downstream")
    assert obs[0]["status"] == "success" and all(row["category"] != "equipment" for row in obs[0]["entities"])
    answer = validate_submission({"direct_facts": [{"ref": "R1"}]}, obs)
    assert answer.ok and not any(f["p"] in ("reaches_nothing", "found_nothing_within_search_limits") for f in answer.facts())
    assert "Nothing" not in answer.render() and "No equipment" not in answer.render()


def test_end_to_end_a_truncated_search_is_rendered_with_its_limit(tools):
    bounded = [call("traverse", start_entity_id="T4750", direction="downstream", entity_types=["equipment"], max_depth=2)]
    agent = PidAgent(ScriptedLLM(bounded, [call("submit_answer", direct_facts=["E1.0"])]), tools, answer_mode="structured")
    result = agent.ask("Is any equipment downstream of T4750?", question_id="t")
    assert result.grounding_status == "grounded"
    assert "within 2 pipe(s) downstream of Tank-1" in result.answer and "does not show that nothing lies beyond" in result.answer
    assert "Nothing of type equipment is downstream" not in result.answer
