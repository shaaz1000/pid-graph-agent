"""Property lookups against values read from C01 (frozen from the real file)."""

from __future__ import annotations

import pytest


def found(service, object_id, name):
    report = service.get_properties(object_id, [name]).properties
    return next(iter(report.values()))["found"]


@pytest.mark.parametrize(
    ("entity_id", "name", "value"),
    [
        ("CentrifugalPump-1", "tagName", "P4711"),
        ("CentrifugalPump-1", "designPressureHead", "10.0 m"),
        ("CentrifugalPump-1", "designRotationalSpeed", "600.0 min-1"),
        ("ReciprocatingPump-1", "designShaftPower", "84.0 kW"),
        ("PlateHeatExchanger-1", "designHeatFlowRate", "313.0 kW"),
        ("PlateHeatExchanger-1", "designHeatTransferArea", "46.8 m2"),
        ("PlateHeatExchanger-1", "plateWidth", "1100.0 mm"),
        ("Tank-1", "cylinderLength", "4.0 m"),
        ("SpringLoadedGlobeSafetyValve-1", "setPressureHigh", "6.0 bar"),
        ("SwingCheckValve-1", "pipingComponentName", "75SA21"),
        ("ProcessInstrumentationFunction-2", "location", "central"),
    ],
)
def test_own_properties(service, entity_id, name, value):
    assert found(service, entity_id, name) == [
        {"property": name, "value": value, "source_object_id": entity_id, "scope": "own"}
    ]


def test_property_names_are_matched_loosely_but_flagged(service):
    items = found(service, "CentrifugalPump-1", "design shaft power")
    assert items[0]["value"] == "60.0 kW" and "match" not in items[0]  # same name, different spelling
    partial = found(service, "CentrifugalPump-1", "shaft power")
    assert partial[0]["property"] == "designShaftPower" and "partial match" in partial[0]["match"]


def test_component_type_is_reported_by_get_entity(service):
    entity = service.get_entity("SwingCheckValve-1").entities[0]
    assert entity["type"] == "SwingCheckValve"
    assert entity["type_hierarchy"][:2] == ["SwingCheckValve", "CheckValve"]


@pytest.mark.parametrize(
    ("connection_id", "line", "segment", "diameter", "fluid", "piping_class"),
    [
        ("PipingNetworkSegment-1/connections/1", "47121", "S1", "DN 80", "MNb", "75HB13"),
        ("PipingNetworkSegment-2/connections/1", "47122", "S1", "DN 80", "MNb", "75HB13"),
        ("PipingNetworkSegment-5/connections/1", "47124", "S2", "DN 80", "MNc", "73HG12"),
        ("PipingNetworkSegment-6/connections/2", "47124", "S3", "DN 50", "MNc", "73HG12"),
        ("PipingNetworkSegment-7/connections/1", "47125", "S1", "DN 25", "MNc", "73HG12"),
        ("PipingNetworkSegment-21/connections/1", "47131", "S1", "DN 50", "WKb", "75HB13"),  # open end
    ],
)
def test_piping_properties(service, connection_id, line, segment, diameter, fluid, piping_class):
    names = ["lineNumber", "segmentNumber", "nominalDiameterRepresentation", "fluidCode", "pipingClassCode"]
    report = service.get_properties(connection_id, names).properties[connection_id]
    assert report["missing"] == []
    assert [item["value"] for item in report["found"]] == [line, segment, diameter, fluid, piping_class]


def test_nominal_diameter_has_three_representations(service):
    values = {i["property"]: i["value"] for i in found(service, "PipingNetworkSegment-2/connections/1", "nominal diameter")}
    assert values == {
        "nominalDiameterNumericalValueRepresentation": "80",
        "nominalDiameterRepresentation": "DN 80",
        "nominalDiameterStandard": "DN 80 (DIN 2448)",
        "nominalDiameterTypeRepresentation": "DN",
    }


def test_component_diameter_comes_from_its_owning_segment(service):
    items = found(service, "BallValve-3", "nominalDiameterRepresentation")
    assert items == [{"property": "nominalDiameterRepresentation", "value": "DN 25", "source_object_id": "PipingNetworkSegment-13", "scope": "owning_segment"}]


def test_line_properties(service):
    assert found(service, "PipingNetworkSystem-2", "lineNumber")[0]["value"] == "47122"
    assert found(service, "PipingNetworkSegment-23", "insulationThickness")[0]["value"] == "80.0 mm"


def test_design_limits_live_on_chambers_and_are_attributed_to_them(service):
    items = found(service, "PlateHeatExchanger-1", "upperLimitDesignPressure")
    assert {(i["source_object_id"], i["value"], i["scope"]) for i in items} == {
        ("Chamber-1", "60.0 bar", "child:Chamber"),
        ("Chamber-2", "30.0 bar", "child:Chamber"),
    }


def test_actuator_fail_action_is_found_on_the_merged_actuator(service):
    items = found(service, "ActuatingFunction-3", "failAction")
    assert items == [{"property": "failAction", "value": "fail open", "source_object_id": "ControlledActuator-3", "scope": "child:ControlledActuator"}]


def test_drawing_metadata(service):
    assert found(service, "MetaData-1", "drawingNumber")[0]["value"] == "123/A93"
    assert found(service, "MetaData-1", "revisionNumber")[0]["value"] == "R2.2"


ABSENT = ["manufacturer", "lastMaintenanceDate", "colour", "operatingPressure", "operatingTemperature", "weight", "serialNumber", "installationDate"]


def test_absent_properties_really_are_absent_from_the_whole_graph(loaded):
    keys = {key.casefold() for _, data in loaded.plant_graph.nodes(data=True) for key in data}
    for word in ("manufactur", "maint", "colour", "color", "operating", "weight", "serial", "install"):
        assert not any(word in key for key in keys), word


@pytest.mark.parametrize("entity_id", ["CentrifugalPump-1", "PlateHeatExchanger-1", "BallValve-1", "Tank-1"])
def test_absent_properties_are_reported_missing(service, entity_id):
    result = service.get_properties(entity_id, ABSENT)
    assert result.status == "empty"
    assert result.properties[entity_id] == {"found": [], "missing": ABSENT, "available": result.properties[entity_id]["available"]}


def test_property_name_with_words_missing_is_a_flagged_partial_match(service):
    """'designFlowRate' is not a DEXPI name; all its words occur in designVolumeFlowRate."""
    items = found(service, "CentrifugalPump-1", "designFlowRate")
    assert [(i["property"], i["value"]) for i in items] == [("designVolumeFlowRate", "200.0 m3/h")]
    assert "partial match" in items[0]["match"]
