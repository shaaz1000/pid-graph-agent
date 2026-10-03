"""Every cross-P&ID question set: its gold facts must be re-derivable from deterministic tool output.

Each suite names its DEXPI file; the same loader, normalizer and tools are used for all of them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pytest

from pid_agent.agent.tools import GraphTools
from pid_agent.graph.service import GraphService

ROOT = Path(__file__).resolve().parents[1]
SUITES = sorted((ROOT / "evals" / "datasets").glob("*/questions.json"))
CASES = [(path.parent.name, question) for path in SUITES for question in json.loads(path.read_text())["questions"]]


@lru_cache(maxsize=None)
def tools_for(suite: str) -> GraphTools:
    pid = json.loads((ROOT / "evals" / "datasets" / suite / "questions.json").read_text())["pid"]
    return GraphTools(GraphService.from_file(ROOT / pid))


def test_suites_exist_and_name_real_files():
    assert len(SUITES) >= 6
    for path in SUITES:
        suite = json.loads(path.read_text())
        assert (ROOT / suite["pid"]).is_file() and 4 <= len(suite["questions"]) <= 8
        assert len({q["id"] for q in suite["questions"]}) == len(suite["questions"])


@pytest.mark.parametrize(("suite", "question"), CASES, ids=[q["id"] for _, q in CASES])
def test_every_gold_fact_is_present_in_deterministic_tool_output(suite, question):
    output = " ".join(json.dumps(tools_for(suite).call(g["tool"], g["args"]).to_dict(), ensure_ascii=False) for g in question["gold"])
    for fact in question["required"]:
        for evidence in fact["evidence"]:
            assert evidence in output, (question["id"], fact["fact"], evidence)
