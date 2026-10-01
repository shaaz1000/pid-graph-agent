"""The evaluation set: gold facts must come from the graph, and the scorer must be sound."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import evaluator  # noqa: E402

QUESTIONS = json.loads(evaluator.QUESTIONS.read_text())["questions"]


def test_fifteen_questions_with_unique_ids():
    assert len(QUESTIONS) == 15 and len({q["id"] for q in QUESTIONS}) == 15
    assert all(q["required"] and q["gold"] for q in QUESTIONS)


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_every_gold_fact_is_present_in_deterministic_tool_output(tools, question):
    """Re-derive the gold: each required fact's evidence string must appear in the output of
    the graph tool calls listed for the question."""
    output = " ".join(json.dumps(tools.call(g["tool"], g["args"]).to_dict(), ensure_ascii=False) for g in question["gold"])
    for fact in question["required"]:
        for evidence in fact["evidence"]:
            assert evidence in output, (question["id"], fact["fact"], evidence)


@pytest.mark.parametrize(
    ("alternative", "answer", "expected"),
    [
        ("DN 80", "the pipe is **DN80**.", True),
        ("DN 80", "the pipe is DN 800.", False),
        ("GlobeValve-2", "via globevalve‑2 (47123/C1)", True),
        ("47126/C2", "BallValve 47126/C21", False),
        ("globe valve", "a Globe-Valve sits there", True),
        (r"re:46\.8\s*m\s*(2|²)", "area of 46.8 m²", True),
        (r"re:(?<![-\d.])0\.1\s*bar", "from −0.1 bar", False),
        (r"re:(?<![-\d.])0\.1\s*bar", "up to 0.1 bar", True),
    ],
)
def test_matching(alternative, answer, expected):
    assert evaluator.matches(alternative, evaluator.normalize(answer)) is expected


def test_partial_credit_and_wrong_fact_penalty():
    question = {"required": [{"fact": "a", "any_of": ["BallValve-4"]}, {"fact": "b", "any_of": ["47126"]}], "forbidden": [{"fact": "x", "any_of": ["BallValve-2"]}]}
    assert evaluator.score_answer(question, "BallValve-4 on line 47126")["score"] == 1.0
    assert evaluator.score_answer(question, "BallValve-4")["score"] == 0.5
    assert evaluator.score_answer(question, "BallValve-4 and BallValve-2 on line 47126")["score"] == 0.5
    assert evaluator.score_answer(question, "nothing relevant")["score"] == 0.0
    assert evaluator.score_answer(question, "BallValve-2")["score"] == 0.0


def test_outcomes():
    question = {"required": [{"fact": "a", "any_of": ["H1007"]}]}
    answered = {"grounding_status": "grounded", "answer": "It is H1007."}
    assert evaluator.judge(question, answered)["outcome"] == "correct"
    assert evaluator.judge(question, {**answered, "answer": "It is H1008."})["outcome"] == "incorrect"
    withheld = evaluator.judge(question, {"grounding_status": "fallback", "answer": "evidence dump mentioning H1007"})
    assert withheld["outcome"] == "abstained" and withheld["score"] == 0.0
    outage = evaluator.judge(question, {"grounding_status": "fallback", "answer": "", "failure_category": "rate_limit"})
    assert outage["outcome"] == "infrastructure_failure" and outage["score"] is None
