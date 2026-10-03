"""Formal evaluation: run the questions once, then score the answers deterministically.

    uv run python evals/evaluator.py            score every saved run (no API key needed)
    uv run python evals/evaluator.py --run      ask the questions once with the configured
                                                provider and model, save the run, then score

    uv run python evals/evaluator.py --dataset-name c02 [--run]
                                                the same for another P&ID: questions from
                                                evals/datasets/c02/questions.json, which names
                                                the DEXPI file; runs under evals/datasets/c02/runs/
    --pid FILE and --questions FILE override the file and the question set.

Without --dataset-name the C01 suite is used exactly as before (evals/questions.json,
evals/runs/). Every suite runs the same agent; only the input file and questions differ.

Each provider/model has its own directory under evals/runs/, so runs never overwrite each
other. ``--run`` never re-asks a question that already has an answer: it only asks questions
that were not reached or that failed for infrastructure reasons, and it stops at the first
provider rate-limit failure so that a spent quota is not hammered.

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
import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
QUESTIONS = HERE / "questions.json"
RUNS = HERE / "runs"
DATASETS = HERE / "datasets"
PROJECT_ROOT = HERE.parent
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


def run_directory(provider: str, model: str, root: Path = RUNS) -> Path:
    return root / re.sub(r"[^a-z0-9.]+", "-", f"{provider}-{model}".lower()).strip("-")


def run_questions(questions: list[dict[str, Any]], pause: float, data_file: Path | None = None, runs_root: Path = RUNS, only: set[str] | None = None) -> Path:
    from pid_agent.agent.tools import GraphTools
    from pid_agent.agent.workflow import PidAgent, format_transcript
    from pid_agent.config import load_settings
    from pid_agent.graph.service import GraphService
    from pid_agent.llm import create_llm

    settings = load_settings()
    data_file = data_file or settings.data_file
    agent = PidAgent(create_llm(settings), GraphTools(GraphService.from_file(data_file)))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    # A run is reproducible from its commit only if the working tree was clean; record that,
    # and a hash of any uncommitted changes to tracked files.
    diff = subprocess.run(["git", "diff", "HEAD"], capture_output=True, cwd=HERE).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "src", "evals/evaluator.py", "evals/questions.json"], capture_output=True, text=True, cwd=HERE).stdout.split()
    dirty = bool(diff) or bool(untracked)
    provenance = {"dirty": dirty, "diff_sha256": hashlib.sha256(diff).hexdigest() if diff else None, "untracked_source_files": untracked}
    directory = run_directory(settings.llm_provider, settings.llm_model, runs_root)
    (directory / "transcripts").mkdir(parents=True, exist_ok=True)
    run_file = directory / "run.json"
    run = {"provider": settings.llm_provider, "model": settings.llm_model, "commit": commit, **provenance, "data_file": str(Path(data_file).resolve().relative_to(PROJECT_ROOT)) if Path(data_file).resolve().is_relative_to(PROJECT_ROOT) else str(data_file), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "results": []}
    if run_file.exists():  # resume: keep every answer already given
        run = json.loads(run_file.read_text())
        run["results"] = [r for r in run["results"] if not r.get("failure_category")]
    answered = {r["question_id"] for r in run["results"]}
    for question in questions:
        if question["id"] in answered or (only is not None and question["id"] not in only):
            continue
        result = agent.ask(question["question"], question_id=question["id"])
        run["results"].append({**result.to_dict(), "answered_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        header = f"Provider: {settings.llm_provider}   Model: {settings.llm_model}   Commit: {commit[:7]}\n\n"
        (directory / "transcripts" / f"{question['id']}.txt").write_text(header + format_transcript(result) + "\n")
        run_file.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
        print(f"ran {question['id']}: {result.grounding_status}, {result.usage['llm_calls']} model calls, failure={result.failure_category}")
        if result.failure_category == "rate_limit":
            print("provider rate limit reached: stopping; the remaining questions were not asked")
            break
        time.sleep(pause)
    return directory


# A question the run never reached (the provider's quota ran out first).
NOT_ASKED = {"failure_category": "not_asked", "answer": "", "grounding_status": "not_validated", "usage": {"llm_calls": 0, "total_tokens": 0}, "trace": [], "duration_ms": 0.0}


def score_run(questions: list[dict[str, Any]], run: dict[str, Any]) -> dict[str, Any]:
    by_id = {r["question_id"]: r for r in run["results"]}
    rows = []
    for question in questions:
        result = by_id.get(question["id"]) or NOT_ASKED
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
    parser.add_argument("--dataset-name", help="a suite under evals/datasets/<name>/ (default: the C01 suite)")
    parser.add_argument("--questions", type=Path, help="question file (default: the suite's questions.json)")
    parser.add_argument("--pid", type=Path, help="DEXPI file to load (default: the file the question set names)")
    parser.add_argument("--only", help="comma-separated question ids to ask, e.g. for a smoke test")
    args = parser.parse_args()
    if args.run or args.dataset_name or args.questions:
        suites = [_suite(args.dataset_name, args.questions, args.pid)]
    else:  # score every saved run of every suite
        suites = [_suite(None, None, None)] + [_suite(p.parent.name, None, None) for p in sorted(DATASETS.glob("*/questions.json"))]
    for questions, data_file, runs_root in suites:
        if args.run:
            only = set(args.only.split(",")) if args.only else None
            directories = [run_questions(questions, args.pause, data_file, runs_root, only)]
        else:
            directories = sorted(p.parent for p in runs_root.glob("*/run.json"))
        for directory in directories:
            report = score_run(questions, json.loads((directory / "run.json").read_text()))
            (directory / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print_report(report)


def _suite(name: str | None, questions_file: Path | None, pid: Path | None) -> tuple[list[dict[str, Any]], Path | None, Path]:
    """(questions, DEXPI file, runs directory) of one suite. No suite has code of its own."""
    if name is None:
        questions_file = questions_file or QUESTIONS
        suite = json.loads(questions_file.read_text())
        return suite["questions"], pid or (PROJECT_ROOT / suite["pid"] if "pid" in suite else None), RUNS
    folder = DATASETS / name
    suite = json.loads((questions_file or folder / "questions.json").read_text())
    return suite["questions"], pid or PROJECT_ROOT / suite["pid"], folder / "runs"


if __name__ == "__main__":
    main()
