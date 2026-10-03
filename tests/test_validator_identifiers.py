"""Grounding validator on identifiers from other DEXPI drawings. No model, no network.

The official DEXPI examples write identifiers C01 does not: tags with spaces ("K 2750"),
superscripts ("PIS⁺Z⁺A275003"), names that contain relation words ("ActuatingFunction-1") and
one loop number shared by several instruments ("031"). Each must be read for what it is, while
everything the validator rejected before is still rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pid_agent.agent.evidence_refs import annotate_refs, check_answer
from pid_agent.agent.grounding import Claim, EvidenceCorpus, extract_claims, identifier_pieces
from pid_agent.agent.tools import GraphTools
from pid_agent.graph.service import GraphService
from test_evidence_refs import ref_of

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "data" / "dexpi-1.3-examples"


def tools_for(name):
    return GraphTools(GraphService.from_file(EXAMPLES / name))


@pytest.fixture(scope="module")
def c02():
    return tools_for("C02V03-VER.EX02.xml")


@pytest.fixture(scope="module")
def i03():
    return tools_for("I03V01-VER.EX01.xml")


@pytest.fixture(scope="module")
def i05():
    return tools_for("I05V01-VER.EX01.xml")


def observe(tools, *calls):
    return [annotate_refs(tools.call(name, arguments).to_dict(), step) for step, (name, arguments) in enumerate(calls, start=1)]


def kinds(text, obs):
    report = check_answer(text, "q", obs)
    return report.level, {p["kind"] for p in report.problems}


# ================================================================== 1. tags with spaces
@pytest.fixture(scope="module")
def column(c02):
    obs = observe(c02, ("get_connections", {"entity_id": "ProcessColumn-1", "relationship": "piping", "direction": "both"}))
    rows = {row["target"]["id"]: row["ref"] for row in obs[0]["connections"]}
    return obs, rows


def test_number_inside_a_written_out_tag_names_the_item(column):
    obs, rows = column
    text = f"Nozzle N1 of K 2750 connects directly to PipeReducer-1, DN 200. [{rows['PipeReducer-1']}]"
    assert check_answer(text, "q", obs).level == "grounded"


@pytest.mark.parametrize(
    "text",
    [
        "PipeReducer-1 is connected with DN 80. [{reducer}]",  # DN 80 of another line
        "BlindFlange-1 is connected with DN 200. [{flange}]",  # DN 200 of another line
        "K 2750 connects to PipeTee-9 with DN 200. [{reducer}]",  # invented entity id
        "K 2750 is on line 9999 with DN 200. [{reducer}]",  # invented line id
        "BlindFlange-1 feeds PipeReducer-1. [{reducer}, {flange}]",  # unsupported relationship
        "PipeReducer-1 feeds K 2750. [{reducer}]",  # reversed direction
        "K 2750 has an upper design pressure of 9.0 bar. [{reducer}]",  # unsupported property value
        "K 2750 connects to PipeReducer-1. [E7.7]",  # nonexistent citation id
    ],
)
def test_spaced_tag_does_not_launder_wrong_facts(column, text):
    obs, rows = column
    level, problems = kinds(text.format(reducer=rows["PipeReducer-1"], flange=rows["BlindFlange-1"]), obs)
    assert level == "insufficient_evidence" and problems, text


# ================================================================== 2. non-ASCII identifiers
def test_answer_and_evidence_cut_identifiers_at_the_same_characters():
    tokens = {c.text for c in extract_claims("PIS⁺Z⁺A275003 and PI(Z)275003A.")}
    assert tokens == {"A275003", "275003A"}
    assert {"a275003", "pis⁺z⁺a275003"} <= identifier_pieces("PIS⁺Z⁺A275003")
    assert {"275003a", "pi", "z"} == identifier_pieces("PI(Z)275003A")
    corpus = EvidenceCorpus([{"evidence": ["PIS⁺Z⁺A275003", "LIC-101"]}])
    assert corpus.supports(Claim("A275003", "identifier", ""))
    assert corpus.supports(Claim("LIC-101", "identifier", ""))
    # distinct identifiers stay distinct
    assert not corpus.supports(Claim("A275004", "identifier", ""))
    assert not corpus.supports(Claim("A2750031", "identifier", ""))
    assert identifier_pieces("PIS⁺Z⁺A275003").isdisjoint(identifier_pieces("PIS⁺Z⁺A275004") - {"pis", "z"})


@pytest.fixture(scope="module")
def signal(c02):
    obs = observe(c02, ("find_entities", {"query": "PI(Z)275003A"}), ("get_connections", {"entity_id": "ProcessInstrumentationFunction-2", "relationship": "instrumentation", "direction": "both"}))
    return obs, ref_of(obs[1], "connections", id="ProcessInstrumentationFunction-1")


def test_superscript_and_ascii_identifiers_are_grounded(signal):
    obs, link = signal
    assert check_answer(f"PI(Z)275003A sends its signal to PIS⁺Z⁺A275003. [{link}]", "q", obs).level == "grounded"
    assert check_answer("PI(Z)275003A is ProcessInstrumentationFunction-2. [E1.1]", "q", obs).level == "grounded"


def test_a_near_miss_of_a_superscript_identifier_is_rejected(signal):
    obs, link = signal
    level, problems = kinds(f"PI(Z)275003A sends its signal to PIS⁺Z⁺A275004. [{link}]", obs)
    assert level == "insufficient_evidence" and problems


# ================================================================== 3. relation words inside names
@pytest.fixture(scope="module")
def loop(i03):
    obs = observe(i03, ("get_connections", {"entity_id": "ProcessInstrumentationFunction-1", "relationship": "instrumentation", "direction": "both"}),
                  ("get_connections", {"entity_id": "ActuatingFunction-1", "relationship": "instrumentation", "direction": "both"}))  # fmt: skip
    return obs, ref_of(obs[0], "connections", id="ActuatingFunction-1"), ref_of(obs[1], "connections", id="GlobeValve-1")


def test_relation_word_inside_a_name_is_not_a_relation(loop):
    obs, signal_link, operates = loop
    text = f"ProcessInstrumentationFunction-1 sends its signal to ActuatingFunction-1, which operates GlobeValve-1. [{signal_link}, {operates}]"
    assert check_answer(text, "q", obs).level == "grounded"


def test_relation_stated_in_prose_is_still_checked(loop):
    obs, signal_link, operates = loop
    assert check_answer(f"ActuatingFunction-1 operates GlobeValve-1. [{operates}]", "q", obs).level == "grounded"
    for text in (f"ProcessInstrumentationFunction-1 operates GlobeValve-1. [{signal_link}, {operates}]", f"GlobeValve-1 operates ActuatingFunction-1. [{operates}]"):
        level, problems = kinds(text, obs)
        assert level == "insufficient_evidence" and "relationship" in problems, text


# ================================================================== 4. shared identifier values
@pytest.fixture(scope="module")
def ratio(i05):
    obs = observe(i05, ("find_entities", {"query": "031"}), ("get_connections", {"entity_id": "ActuatingFunction-1", "relationship": "instrumentation", "direction": "both"}))
    rows = {e["id"]: e["ref"] for e in obs[0]["entities"]}
    return obs, rows, ref_of(obs[1], "connections", id="GlobeValve-1")


def test_shared_loop_number_stated_about_the_items_that_carry_it(ratio):
    obs, rows, _ = ratio
    text = f"Loop 031 contains FI031.1 and FI031.2. [{rows['ProcessInstrumentationFunction-4']}, {rows['ProcessInstrumentationFunction-3']}]"
    assert check_answer(text, "q", obs).level == "grounded"
    assert check_answer("031 matches several instrument functions. [E1.0]", "q", obs).level == "ambiguous"


@pytest.mark.parametrize(
    "text",
    [
        "Loop 031 ultimately actuates GlobeValve-1. [{valve}]",  # no named item carries 031 in the cited facts
        "FI031.1 belongs to loop 031. [{valve}]",  # the item is named, but the cited row is not about it
        "GlobeValve-1 belongs to loop 031. [{pif1}]",  # 031 exists, but not for the item named
        "Loop 031 is the level loop. [R2]",  # ambiguous, no relationship evidence at all
    ],
)
def test_shared_identifier_without_its_owner_is_still_ambiguous(ratio, text):
    obs, rows, valve = ratio
    level, problems = kinds(text.format(valve=valve, pif1=rows["ProcessInstrumentationFunction-1"]), obs)
    assert level == "insufficient_evidence" and problems, text
