"""The official DEXPI 1.3 example files go through the same pipeline as C01, with no file-specific code."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from pid_agent.graph.normalizer import normalize
from pid_agent.graph.service import GraphService
from pid_agent.ingestion.dexpi_loader import load_plant
from pid_agent.main import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "data" / "dexpi-1.3-examples").glob("*.xml"))


def test_all_official_examples_are_present_unchanged_in_count():
    assert len(EXAMPLES) == 34  # plus C01 at data/, 35 in total


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_every_example_completes_every_ingestion_stage(path):
    index = normalize(load_plant(path))
    GraphService(index)
    assert index.entities
    assert not [w for w in index.warnings if "SignalLineFunction" in w]


@pytest.mark.parametrize(
    ("name", "links"),
    [
        ("I03V01-VER.EX01.xml", {("ProcessInstrumentationFunction-1", "ActuatingFunction-1")}),
        ("I05V01-VER.EX01.xml", {("ProcessInstrumentationFunction-1", "ActuatingFunction-1"), ("ProcessInstrumentationFunction-2", "ProcessInstrumentationFunction-1"),
                                 ("ProcessInstrumentationFunction-3", "ProcessInstrumentationFunction-2"), ("ProcessInstrumentationFunction-4", "ProcessInstrumentationFunction-2")}),
        ("I12V01-VER.EX01.xml", None),
    ],
)
def test_signal_line_function_becomes_the_same_signal_link_as_signal_conveying_function(name, links):
    index = normalize(load_plant(ROOT / "data" / "dexpi-1.3-examples" / name))
    signals = {(c.source, c.target) for c in index.connections.values() if c.connection_type == "signal_line"}
    assert signals and (links is None or signals == links)
    assert all(c.relationship == "instrumentation" for c in index.connections.values() if c.connection_type == "signal_line")


def test_signal_links_of_c01_are_unchanged(index):
    signals = {(c.source, c.target) for c in index.connections.values() if c.connection_type == "signal_line"}
    assert signals == {("ProcessInstrumentationFunction-2", "ActuatingFunction-1"), ("ProcessInstrumentationFunction-3", "ActuatingFunction-2"), ("ProcessInstrumentationFunction-4", "ActuatingFunction-3")}


def test_signal_chain_is_now_answerable_by_the_tools():
    from pid_agent.agent.tools import GraphTools

    tools = GraphTools(GraphService.from_file(ROOT / "data" / "dexpi-1.3-examples" / "I03V01-VER.EX01.xml"))
    links = tools.call("get_connections", {"entity_id": "LICSA03", "relationship": "instrumentation"}).to_dict()["connections"]
    assert any(c["connection_type"] == "signal_line" and c["target"]["id"] == "ActuatingFunction-1" for c in links)


def test_cli_selects_any_dexpi_file_with_pid(capsys):
    target = ROOT / "data" / "dexpi-1.3-examples" / "C03V04-VER.EX02.xml"
    assert main(["--pid", str(target), "tool", "find_entities", '{"query": "ESV3712"}']) == 0
    assert '"ProcessInstrumentationFunction-1"' in capsys.readouterr().out
    assert main(["--pid", str(target), "tool", "find_entities", '{"query": "P4711"}']) == 0
    assert '"not_found"' in capsys.readouterr().out  # no C01 entity leaks into another drawing


def test_evaluator_suites_are_generic():
    spec = importlib.util.spec_from_file_location("evaluator", ROOT / "evals" / "evaluator.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    questions, pid, runs = evaluator._suite(None, None, None)  # the C01 default is unchanged
    assert len(questions) == 15 and pid is None and runs == evaluator.RUNS
    questions, pid, runs = evaluator._suite("c03", None, None)
    assert pid == ROOT / "data" / "dexpi-1.3-examples" / "C03V04-VER.EX02.xml" and runs == evaluator.DATASETS / "c03" / "runs"
    other = ROOT / "data" / "dexpi-1.3-examples" / "P04V01-VER.EX01.xml"
    assert evaluator._suite("c03", None, other)[1] == other
    assert evaluator.run_directory("nvidia", "nvidia/x", runs).parent == runs
    source = (ROOT / "evals" / "evaluator.py").read_text() + (ROOT / "src" / "pid_agent" / "graph" / "normalizer.py").read_text()
    for name in ("c02", "c03", "i03", "i05", "e06", "e12", "p02", "p04", "C02V03", "I03V01"):
        assert f'"{name}"' not in source  # no suite or file is named in code
