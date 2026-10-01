"""Deterministic entity resolution: tiers, ambiguity and refusal to guess."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def resolve(service):
    return service.resolver.resolve


def tiers(resolution):
    return {m.tier for m in resolution.matches}


def test_exact_tag(resolve):
    r = resolve("P4711")
    assert r.entity_ids == ["CentrifugalPump-1"] and tiers(r) == {"exact_tag"}
    assert r.matches[0].confidence == 1.0 and not r.ambiguous and r.status == "unique"


def test_h1007_exact_tag(resolve):
    assert resolve("H1007").entity_ids == ["PlateHeatExchanger-1"]


def test_case_insensitive_tag(resolve):
    r = resolve("p4711")
    assert r.entity_ids == ["CentrifugalPump-1"] and tiers(r) == {"tag_case_insensitive"}


def test_proteus_id(resolve):
    r = resolve("ballvalve-3")
    assert r.entity_ids == ["BallValve-3"] and tiers(r) == {"proteus_id"}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("SV 104.01", "SpringLoadedGlobeSafetyValve-1"),
        ("sv104.01", "SpringLoadedGlobeSafetyValve-1"),
        ("75SA21", "SwingCheckValve-1"),
        ("PT4712.01", "ProcessSignalGeneratingFunction-1"),
        ("TV4750.03", "ActuatingFunction-3"),
        ("4750.03", "ProcessInstrumentationFunction-4"),
        ("TICSA 4750.03", "ProcessInstrumentationFunction-4"),
        ("47126/C5", "BallValve-3"),
        ("47122", "PipingNetworkSystem-2"),
        ("PV4712.02_YV", "GlobeValve-1"),
    ],
)
def test_non_tag_identifiers(resolve, query, expected):
    r = resolve(query)
    assert r.entity_ids == [expected] and tiers(r) == {"identifier"} and not r.ambiguous


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("pump P4711", "CentrifugalPump-1"),
        ("heat exchanger H1007", "PlateHeatExchanger-1"),
        ("the tank T4750 please", "Tank-1"),
        ("safety valve SV 104.01", "SpringLoadedGlobeSafetyValve-1"),
    ],
)
def test_identifier_embedded_in_a_phrase(resolve, query, expected):
    r = resolve(query)
    assert r.entity_ids == [expected] and tiers(r) == {"embedded_identifier"} and not r.warnings


def test_shared_component_code_stays_ambiguous(resolve):
    r = resolve("73KH12")
    assert sorted(r.entity_ids) == [f"BallValve-{i}" for i in range(1, 6)]
    assert r.ambiguous and r.status == "multiple"


def test_component_number_is_ambiguous_without_a_line(resolve):
    r = resolve("C1")
    assert len(r.matches) == 5 and r.ambiguous


def test_line_context_disambiguates_component_number(resolve):
    assert resolve("C1 on line 47127").entity_ids == ["GlobeValve-1"]
    assert resolve("C1 on line 47126").entity_ids == ["PipeTee-2"]
    assert not resolve("C1 on line 47127").ambiguous


def test_line_context_that_contradicts_the_identifier_is_reported(resolve):
    r = resolve("C11 on line 47124")  # C11 only exists on 47126
    assert set(r.entity_ids) == {"BlindFlange-2", "PipingNetworkSystem-4"}
    assert any("do not refer to the same item" in w for w in r.warnings)


def test_type_word_that_contradicts_the_identifier_is_reported(resolve):
    r = resolve("valve P4711")
    assert r.entity_ids == ["CentrifugalPump-1"]
    assert any("'valve'" in w for w in r.warnings)


def test_several_identifiers_in_one_query(resolve):
    r = resolve("P4711 and H1007")
    assert r.entity_ids == ["CentrifugalPump-1", "PlateHeatExchanger-1"] and not r.ambiguous


def test_plural_type_is_a_set_not_an_ambiguity(resolve):
    r = resolve("all pumps")
    assert r.entity_ids == ["CentrifugalPump-1", "ReciprocatingPump-1"]
    assert tiers(r) == {"type"} and not r.ambiguous


def test_singular_type_with_several_candidates_is_ambiguous(resolve):
    r = resolve("the heat exchanger")
    assert r.entity_ids == ["PlateHeatExchanger-1", "TubularHeatExchanger-1"] and r.ambiguous


def test_singular_type_with_one_candidate_is_unique(resolve):
    r = resolve("the tank")
    assert r.entity_ids == ["Tank-1"] and not r.ambiguous


def test_specific_type_phrase(resolve):
    assert resolve("check valves").entity_ids == ["SwingCheckValve-1"]
    assert len(resolve("globe valves").entity_ids) == 3  # the safety valve is not a GlobeValve


def test_description_needing_semantics_stays_ambiguous(resolve):
    r = resolve("the heat exchanger after the pump")
    assert r.ambiguous and len(r.matches) == 4
    assert any("after" in w for w in r.warnings)


def test_unmatched_descriptor_does_not_silently_narrow(resolve):
    r = resolve("red valve")
    assert len(r.matches) == 11 and r.ambiguous
    assert any("red" in w for w in r.warnings)


@pytest.mark.parametrize("query", ["X9999", "P9999", "K-101", "compressor", "", "   "])
def test_unknown_things_resolve_to_nothing(resolve, query):
    r = resolve(query)
    assert r.matches == [] and r.status == "none" and not r.ambiguous


def test_near_miss_is_suggested_but_never_bound(resolve):
    r = resolve("P4771")
    assert r.matches == []
    assert {s["id"] for s in r.suggestions} == {"CentrifugalPump-1", "ReciprocatingPump-1"}


def test_entity_type_argument_filters(resolve):
    assert resolve("C1", entity_type="globe valve").entity_ids == ["GlobeValve-2", "GlobeValve-1", "GlobeValve-3"]
    assert resolve("pump", entity_type="valve").matches == []


def test_entity_type_argument_never_hides_an_identifier_match(resolve):
    r = resolve("P4711", entity_type="valve")
    assert r.entity_ids == ["CentrifugalPump-1"]
    assert any("does not fit the identifier match CentrifugalPump-1 (CentrifugalPump)" in w for w in r.warnings)


def test_entity_type_argument_alone_lists_the_type(resolve):
    assert resolve("", entity_type="pump").entity_ids == ["CentrifugalPump-1", "ReciprocatingPump-1"]


def test_unknown_entity_type_argument(resolve):
    r = resolve("H1007", entity_type="heater")
    assert r.entity_ids == ["PlateHeatExchanger-1"]
    assert any("Unknown entity_type 'heater'" in w and "ignored" in w for w in r.warnings)
    untyped = resolve("", entity_type="spaceship")
    assert untyped.matches == [] and any("Unknown entity_type" in w for w in untyped.warnings)
    assert resolve("pump", entity_type="spaceship").matches == []


# ------------------------------------------------- identifier provenance
def test_source_identifier_is_reported_as_a_plain_field(service):
    entity = service.find_entities("SV 104.01").entities[0]
    assert entity["identifier_kind"] == "source_identifier"
    assert entity["match_reason"] == "positionNumber = 'SV 104.01'"
    assert "identifier_notes" not in entity


def test_derived_identifier_says_it_is_derived(service):
    entity = service.find_entities("PICSA4712.02").entities[0]
    assert entity["id"] == "ProcessInstrumentationFunction-2"
    assert entity["identifier_kind"] == "derived_identifier"
    assert entity["match_reason"].startswith("derived identifier instrumentTag = 'PICSA4712.02'")
    assert "not a literal field in the DEXPI file" in entity["match_reason"]
    assert entity["identifier_notes"]["instrumentTag"].startswith("derived_identifier: composed from")


def test_line_component_identifier_is_derived(service):
    entity = service.find_entities("47126/C5").entities[0]
    assert entity["identifier_kind"] == "derived_identifier"
    assert "PipingNetworkSystem-6" in entity["match_reason"]


def test_alias_names_the_object_it_comes_from(service):
    entity = service.find_entities("PV4712.02_YV").entities[0]
    assert entity["id"] == "GlobeValve-1" and entity["identifier_kind"] == "alias"
    assert "OperatedValveReference-1" in entity["match_reason"]


def test_every_non_source_identifier_has_an_origin(index):
    source_fields = {"tagName", "positionNumber", "pipingComponentName", "pipingComponentNumber",
                     "processInstrumentationFunctionNumber", "processSignalGeneratingFunctionNumber",
                     "actuatingFunctionNumber", "lineNumber"}
    for entity in index.entities.values():
        for key, value in entity.identifiers.items():
            if key in source_fields:
                assert entity.properties[key] == value  # literally present on the object
                assert key not in entity.identifier_origins
            else:
                assert entity.identifier_origins[key].kind in ("derived_identifier", "alias")
