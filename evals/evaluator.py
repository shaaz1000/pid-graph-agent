"""Formal evaluation: run the questions once, then score the answers deterministically.

    uv run python evals/evaluator.py            score the saved run (no API key needed)
    uv run python evals/evaluator.py --run      ask every question once, save the run, then score

Scoring (no LLM judge): every question lists required facts taken from the graph, and
optionally forbidden ones (wrong or invented facts).

    score = max(0, required facts found - forbidden facts found) / required facts

A fact is "found" when any of its accepted spellings occurs in the answer; matching ignores
case, markdown emphasis, typographic dashes and spacing/hyphenation inside an identifier
("DN80" = "DN 80"). An answer that the agent itself withheld (grounding fallback) scores 0 and
is reported as "abstained". A provider failure is reported as "infrastructure_failure" and
is left out of the average.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
QUESTIONS = HERE / "questions.json"
RUN = HERE / "run.json"
RESULTS = HERE / "results.json"
TRANSCRIPTS = HERE / "transcripts"
TYPOGRAPHY = str.maketrans({"−": "-", "‑": "-", "‐": "-", "–": "-", "—": "-", " ": " ", " ": " ", " ": " "})


def normalize(text: str) -> str:
    text = text.translate(TYPOGRAPHY).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text))


def matches(alternative: str, answer: str) -> bool:
    """``re:`` alternatives are regular expressions; others are literal words or identifiers."""
    if alternative.startswith("re:"):
        return re.search(alternative[3:].casefold(), answer) is not None
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", normalize(alternative)) if p]
    return re.search(r"(?<![a-z0-9])" + r"[\s\-]*".join(parts) + r"(?![a-z0-9])", answer) is not None


def score_answer(question: dict[str, Any], answer: str) -> dict[str, Any]:
    text = normalize(answer)
    required = [{"fact": f["fact"], "found": any(matches(a, text) for a in f["any_of"])} for f in question["required"]]
    forbidden = [{"fact": f["fact"], "found": any(matches(a, text) for a in f["any_of"])} for f in question.get("forbidden", [])]
    found = sum(f["found"] for f in required)
    wrong = sum(f["found"] for f in forbidden)
    return {"score": round(max(0, found - wrong) / len(required), 3), "required": required, "forbidden": forbidden}


def judge(question: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    if result.get("failure_category"):
        return {"score": None, "outcome": "infrastructure_failure", "required": [], "forbidden": []}
    if result["grounding_status"] == "fallback":
        scored = score_answer(question, "")
        return {**scored, "score": 0.0, "outcome": "abstained"}
    scored = score_answer(question, result["answer"])
    outcome = "correct" if scored["score"] == 1 else "partially_correct" if scored["score"] > 0 else "incorrect"
    return {**scored, "outcome": outcome}


def run_questions(questions: list[dict[str, Any]], pause: float) -> dict[str, Any]:
    from pid_agent.agent.tools import GraphTools
    from pid_agent.agent.workflow import PidAgent, format_transcript
    from pid_agent.config import load_settings
    from pid_agent.graph.service import GraphService
    from pid_agent.llm import create_llm

    settings = load_settings()
    agent = PidAgent(create_llm(settings), GraphTools(GraphService.from_file(settings.data_file)))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    run = {"provider": settings.llm_provider, "model": settings.llm_model, "commit": commit, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "results": []}
    TRANSCRIPTS.mkdir(exist_ok=True)
    for question in questions:
        result = agent.ask(question["question"], question_id=question["id"])
        run["results"].append(result.to_dict())
        header = f"Provider: {settings.llm_provider}   Model: {settings.llm_model}   Commit: {commit[:7]}\n\n"
        (TRANSCRIPTS / f"{question['id']}.txt").write_text(header + format_transcript(result) + "\n")
        RUN.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
        print(f"ran {question['id']}: {result.grounding_status}, {result.usage['llm_calls']} model calls")
        time.sleep(pause)
    return run


def score_run(questions: list[dict[str, Any]], run: dict[str, Any]) -> dict[str, Any]:
    by_id = {r["question_id"]: r for r in run["results"]}
    rows = []
    for question in questions:
        result = by_id[question["id"]]
        verdict = judge(question, result)
        rows.append({
            "id": question["id"],
            "category": question["category"],
            "question": question["question"],
            "expected": [f["fact"] for f in question["required"]],
            "answer": result["answer"],
            **verdict,
            "model_calls": result["usage"]["llm_calls"],
            "tool_calls": sum(1 for step in result["trace"] if step.get("executed", True)),
            "tokens": result["usage"]["total_tokens"],
            "latency_ms": result["duration_ms"],
            "grounding": result["grounding_status"],
            "regenerated": bool(result.get("rejected_drafts")),
            "fallback": result["grounding_status"] == "fallback",
            "turn_limit": result.get("limit_reached"),
            "unsupported_claims": [c["claim"] for c in result.get("unsupported_claims", [])],
        })
    scored = [r["score"] for r in rows if r["score"] is not None]
    outcomes: dict[str, int] = {}
    for row in rows:
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
    return {
        "provider": run["provider"],
        "model": run["model"],
        "commit": run["commit"],
        "questions": len(rows),
        "scored_questions": len(scored),
        "mean_score": round(sum(scored) / len(scored), 3) if scored else None,
        "outcomes": outcomes,
        "totals": {key: sum(r[key] for r in rows) for key in ("model_calls", "tool_calls", "tokens")},
        "rows": rows,
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"\nprovider={report['provider']}  model={report['model']}  commit={report['commit'][:7]}\n")
    print(f"{'id':8} {'score':>5}  {'outcome':17} {'calls':>5} {'tools':>5} {'tokens':>6}  grounding    question")
    for r in report["rows"]:
        score = "  n/a" if r["score"] is None else f"{r['score']:5.2f}"
        print(f"{r['id']:8} {score}  {r['outcome']:17} {r['model_calls']:5d} {r['tool_calls']:5d} {r['tokens']:6d}  {r['grounding']:12} {r['question'][:60]}")
        for fact in r["required"]:
            if not fact["found"]:
                print(f"{'':16}missing: {fact['fact']}")
        for fact in r["forbidden"]:
            if fact["found"]:
                print(f"{'':16}wrong:   {fact['fact']}")
    print(f"\nmean score: {report['mean_score']} over {report['scored_questions']} of {report['questions']} questions   outcomes: {report['outcomes']}")
    print(f"totals: {report['totals']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="ask the agent every question once before scoring")
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between questions when running")
    args = parser.parse_args()
    questions = json.loads(QUESTIONS.read_text())["questions"]
    run = run_questions(questions, args.pause) if args.run else json.loads(RUN.read_text())
    report = score_run(questions, run)
    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print_report(report)


if __name__ == "__main__":
    main()
