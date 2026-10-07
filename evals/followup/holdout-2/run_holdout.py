"""Runs and scores the holdout with the unchanged follow-up evaluator.

    uv run python evals/followup/holdout/run_holdout.py --run     8 questions once, 16 phrasings twice
    uv run python evals/followup/holdout/run_holdout.py           score the saved runs
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import followup  # noqa: E402

questions = json.loads((HERE / "questions.json").read_text())["questions"]
groups = json.loads((HERE / "groups.json").read_text())["groups"]
root = HERE / "runs"
if "--run" in sys.argv:
    followup.run("complex", questions, 1, root, 1.0)
    followup.run("consistency", followup.phrasing_items(groups), 2, root, 1.0)
for run_file in sorted(root.glob("*/*/run.json")):
    record = json.loads(run_file.read_text())
    report = followup.report_complex(questions, record) if record["suite"] == "complex" else followup.report_consistency(groups, record)
    (run_file.parent / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (followup.print_complex if record["suite"] == "complex" else followup.print_consistency)(report)
