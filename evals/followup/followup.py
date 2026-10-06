"""Follow-up evaluation: complex questions and consistency under rephrasing.

    uv run python evals/followup/followup.py                         score every saved run (no key)
    uv run python evals/followup/followup.py --run complex           ask each complex question once
    uv run python evals/followup/followup.py --run consistency --repeats 3
                                                                     ask every phrasing 3 times,
                                                                     each as its own turn
    uv run python evals/followup/followup.py --run smoke             the small subset

Nothing here reads answer text. The agent answers with ``submit_answer``: evidence rows and
what the P&ID does not establish. An answer is the set of canonical facts of the rows it
cites, plus the categories of its unknowns.

Gold (complex/questions.json, consistency/groups.json): each required item is a fact pattern,
or a list of equivalent patterns, that a graph operation produces; ``tests/test_followup.py``
re-derives every pattern from the graph. An item can also be an ``unknown``: a category the
answer must name as not established by the P&ID (a closure order, a pressure response).

Complex score: required items found / required items. Extra correct facts cost nothing.

Consistency, for a group of phrasings that ask the same thing. Each run is reduced to its
*profile*: which required items it found, and which unknown categories it named.

* repeat consistency     the repeats of one phrasing have the same profile
* cross-phrasing         every run of the group has the same profile
* contradictions         the same object and property (or relation) with different values in
                         two runs, unless the drawing itself gives that slot several values
* entity resolution      every run found the items the question names (its input), whether
                         or not it then reached the items of the answer
* required-fact recall   mean share of required items found
* Jaccard overlap        of the full cited fact sets; descriptive only, extra facts are allowed

Every run that misses a required item is classified by cause, from its trace.

Correctness and consistency are judged against different things. A group's ``required`` is
the semantic target all its phrasings share, and consistency is measured against it. A single
phrasing can carry its own ``required`` when its literal wording asks for less (for example
"map all connections for X" can be read as the direct connections of X): its correctness is
then judged against that, so a literally valid answer is not called wrong.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pid_agent.agent.answer import EvidenceRegistry, fact_key  # noqa: E402
from pid_agent.agent.evidence_refs import annotate_refs  # noqa: E402
from pid_agent.graph.service import same_value  # noqa: E402

COMPLEX = HERE / "complex" / "questions.json"
GROUPS = HERE / "consistency" / "groups.json"
SMOKE = {"complex": ["C1", "C8", "C7"], "groups": {"R1": ["R1a", "R1b", "R1c", "R1d"], "R3": ["R3a", "R3b", "R3c", "R3d"]}}
# One value per subject (and property): two different values in a group are a contradiction.
FUNCTIONAL = {"has_property", "loop_acts_on", "loop_measured_at", "fully_valve_bounded", "relief_path_inside_boundary"}
LIST_KEYS = ("entities", "elements", "components")


# ------------------------------------------------------------------ fact patterns
def _text_equal(actual: Any, wanted: Any) -> bool:
    if isinstance(wanted, bool) or isinstance(actual, bool):
        return str(actual).lower() == str(wanted).lower()
    return same_value(actual, wanted)


def matches(pattern: dict[str, Any], fact: dict[str, Any]) -> bool:
    """Whether a canonical fact fits a gold pattern. Only the keys a pattern gives are compared."""
    q = fact.get("q") or {}
    members = [i for name in LIST_KEYS for i in q.get(name) or []]
    for name, wanted in pattern.items():
        if name == "p":
            ok = fact["p"] in (wanted if isinstance(wanted, list) else [wanted])
        elif name == "s":  # the object that carries the fact, or the item that object belongs to
            ok = wanted in (fact.get("s"), q.get("owner"))
        elif name == "o":
            ok = fact.get(name) == wanted
        elif name == "v":
            ok = "v" in fact and _text_equal(fact["v"], wanted)
        elif name == "ends":  # a relation between two items, in either direction
            ok = {fact.get("s"), fact.get("o")} == set(wanted)
        elif name == "q":
            ok = all(k in q and (q[k] == v if isinstance(v, list) else _text_equal(q[k], v)) for k, v in wanted.items())
        elif name == "contains":  # items on a route, a chain or a run
            ok = all(i in members for i in wanted)
        elif name == "blocked_contains":
            ok = wanted in (q.get("blocked") or [])
        elif name == "blocked_absent":
            ok = not q.get("blocked")
        else:
            raise ValueError(f"unknown pattern key '{name}'")
        if not ok:
            return False
    return True


def found(item: dict[str, Any], facts: list[dict[str, Any]], unknowns: set[str]) -> bool:
    """An item is a fact (any of several equivalent patterns), an unknown category, or either."""
    if unknowns & set(item.get("unknown", [])):
        return True
    return any(matches(pattern, fact) for pattern in item.get("any_of", []) for fact in facts)


# ------------------------------------------------------------------ gold from the graph
def gold_facts(tools: Any, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Canonical facts of the given tool calls, exactly as the agent's evidence registry builds them."""
    observations = [annotate_refs(tools.call(c["tool"], c["args"]).to_dict(), step) for step, c in enumerate(calls, start=1)]
    return EvidenceRegistry(observations).all_facts()


# ------------------------------------------------------------------ one answer
def answer_facts(result: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    submission = result.get("submission") or {}
    facts: dict[str, dict[str, Any]] = {}
    for item in [*submission.get("direct_facts", []), *submission.get("derived_facts", [])]:
        for fact in item["facts"]:
            facts.setdefault(fact_key(fact), fact)
    return list(facts.values()), {u["category"] for u in submission.get("unknowns", [])}


def evidence_facts(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Everything the tool calls of a run returned, whether the answer cited it or not."""
    observations = result.get("tool_results") or []
    return EvidenceRegistry(observations).all_facts() if observations else []


def anchors_resolved(gold: dict[str, Any], result: dict[str, Any]) -> bool:
    """Whether the run found every item the question names (``anchors``) in some tool result."""
    seen = {i for fact in evidence_facts(result) for i in (fact.get("s"), fact.get("o"), (fact.get("q") or {}).get("owner")) if i}
    for observation in result.get("tool_results") or []:
        seen.update(e["id"] for e in observation.get("entities") or [] if "id" in e)
    return all(anchor in seen for anchor in gold.get("anchors", []))


def judge(gold: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    required = gold["required"]
    if result.get("failure_category"):
        return {"outcome": "provider_failure", "score": None, "profile": None, "required": [], "forbidden": []}
    facts, unknowns = answer_facts(result)
    rows = [{"item": item.get("fact") or f"unknown: {' / '.join(item['unknown'])}", "kind": "fact" if "any_of" in item else "unknown", "found": found(item, facts, unknowns)} for item in required]
    forbidden = [f["fact"] for f in gold.get("forbidden", []) if any(matches(p, fact) for p in f["any_of"] for fact in facts)]
    hits = sum(r["found"] for r in rows)
    withheld = not result.get("submission")
    score = 0.0 if withheld else round(hits / len(rows), 3)
    outcome = "withheld" if withheld else "incorrect" if forbidden or hits == 0 else "correct" if hits == len(rows) else "partial"
    return {"outcome": outcome, "score": score, "profile": [r["found"] for r in rows], "required": rows, "forbidden": forbidden,
            "unknown_categories": sorted(unknowns), "cited_facts": len(facts)}  # fmt: skip


def cause(gold: dict[str, Any], result: dict[str, Any], verdict: dict[str, Any]) -> str:
    """Why a run misses required items, read from its trace."""
    if result.get("failure_category"):
        return "provider/model variance"
    if not result.get("submission"):
        return "grounding rejection" if any(s["tool"] == "submit_answer" for s in result.get("trace", [])) else "answer synthesis"
    available = evidence_facts(result)
    # Resolution is about the items the question names. Not reaching an item of the answer
    # afterwards is a planning or traversal miss, handled below.
    if not anchors_resolved(gold, result):
        ambiguous = any(s.get("status") == "ambiguous" for s in result.get("trace", []))
        return "ambiguity in the question" if ambiguous else "entity resolution"
    missing = [item for item, row in zip(gold["required"], verdict["required"]) if not row["found"]]
    if any("any_of" in item and not found(item, available, set()) for item in missing):
        return "incomplete traversal" if result.get("limit_reached") else "planner/tool choice"
    return "answer synthesis"  # the facts were retrieved (or only an unknown is missing) but not submitted


# ------------------------------------------------------------------ running
def _provenance() -> dict[str, Any]:
    def git(*args: str) -> bytes:
        return subprocess.run(["git", *args], capture_output=True, cwd=PROJECT_ROOT).stdout

    diff = git("diff", "HEAD")
    # Source and gold only: the files a run writes are not part of what was evaluated.
    untracked = git("ls-files", "--others", "--exclude-standard", "src", "evals/followup/followup.py", "evals/followup/build_gold.py", "evals/followup/complex", "evals/followup/consistency").decode().split()
    return {"commit": git("rev-parse", "HEAD").decode().strip(), "dirty": bool(diff) or bool(untracked), "diff_sha256": hashlib.sha256(diff).hexdigest() if diff else None,
            "untracked_source_files": untracked}  # fmt: skip


def _slug(provider: str, model: str) -> str:
    return "".join(c if c.isalnum() or c == "." else "-" for c in f"{provider}-{model}".lower()).strip("-")


def run(suite: str, items: list[dict[str, Any]], repeats: int, root: Path, pause: float) -> Path:
    """Ask each item ``repeats`` times, every time as a new, independent turn."""
    from pid_agent.agent.tools import GraphTools
    from pid_agent.agent.workflow import PidAgent, format_transcript
    from pid_agent.config import load_settings
    from pid_agent.graph.service import GraphService
    from pid_agent.llm import create_llm

    settings = load_settings()
    agent = PidAgent(create_llm(settings), GraphTools(GraphService.from_file(settings.data_file)), answer_mode="structured")
    directory = root / _slug(settings.llm_provider, settings.llm_model) / suite
    (directory / "transcripts").mkdir(parents=True, exist_ok=True)
    run_file = directory / "run.json"
    record = {"run_id": time.strftime("%Y%m%dT%H%M%S"), "suite": suite, "provider": settings.llm_provider, "model": settings.llm_model, "temperature": 0.0,
              "answer_mode": "structured", "repeats": repeats, **_provenance(), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "results": []}  # fmt: skip
    if run_file.exists():  # resume: keep every answer already given, ask again only what failed for the provider
        record = json.loads(run_file.read_text())
        record["results"] = [r for r in record["results"] if not r.get("failure_category")]
    done = {(r["question_id"], r["repeat"]) for r in record["results"]}
    for item in items:
        for repeat in range(1, repeats + 1):
            if (item["id"], repeat) in done:
                continue
            result = agent.ask(item["question"], question_id=item["id"])
            data = result.to_dict()
            # The full tool results are kept so that a run can be re-scored and its misses explained.
            data["tool_results"] = agent.last_observations
            record["results"].append({**data, "group": item.get("group"), "repeat": repeat, "answered_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            name = item["id"] + (f"_r{repeat}" if repeats > 1 else "")
            header = f"Provider: {settings.llm_provider}   Model: {settings.llm_model}   Commit: {record['commit'][:7]}   Repeat: {repeat}\n\n"
            (directory / "transcripts" / f"{name}.txt").write_text(header + format_transcript(result) + "\n")
            run_file.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
            print(f"ran {item['id']} r{repeat}: {result.grounding_status}, {result.usage['llm_calls']} model calls, {result.duration_ms / 1000:.1f} s, failure={result.failure_category}", flush=True)
            if result.failure_category == "rate_limit":
                print("provider rate limit reached: stopping; the remaining questions were not asked")
                return directory
            time.sleep(pause)
    return directory


# ------------------------------------------------------------------ reports
def _efficiency(results: list[dict[str, Any]]) -> dict[str, Any]:
    seconds = [r["duration_ms"] / 1000 for r in results if not r.get("failure_category")]
    return {"runs": len(results), "llm_calls": sum(r["usage"].get("llm_calls", 0) for r in results), "tool_calls": sum(1 for r in results for s in r["trace"] if s.get("executed", True)),
            "tokens": sum(r["usage"].get("total_tokens", 0) for r in results), "median_latency_s": round(statistics.median(seconds), 1) if seconds else None,
            "mean_latency_s": round(statistics.mean(seconds), 1) if seconds else None}  # fmt: skip


def _grounding(results: list[dict[str, Any]]) -> dict[str, Any]:
    submissions = [r["submission"] for r in results if r.get("submission")]
    return {"structured_answers": len(submissions), "withheld": sum(1 for r in results if not r.get("submission") and not r.get("failure_category")),
            "provider_failures": sum(1 for r in results if r.get("failure_category")),
            "rejected_submissions": sum(1 for r in results for s in r["trace"] if s["tool"] == "submit_answer" and s["status"] == "rejected"),
            # The one structured-output repair after a rejected final submission.
            "final_repairs": {"attempted": sum(1 for r in results if (r.get("repair") or {}).get("attempted")), "succeeded": sum(1 for r in results if (r.get("repair") or {}).get("succeeded"))},
            # Requested outputs (from the decomposition of each question) and how they were accounted for.
            "requested_outputs": {"total": sum(len(s.get("requested_outputs") or []) for s in submissions),
                                  "covered_by_facts": sum(1 for s in submissions for o in s.get("requested_outputs") or [] if o["covered_by"].get("direct") or o["covered_by"].get("derived")),
                                  "marked_unknown": sum(1 for s in submissions for o in s.get("requested_outputs") or [] if o["covered_by"].get("unknown")),
                                  "unaccounted": sum(1 for s in submissions for o in s.get("requested_outputs") or [] if o["covered_by"] is None)},
            # Structural: a cited id either exists in the tool results or the submission is rejected.
            "unsupported_facts_in_answers": 0,
            # No text written by the model is rendered; this counts answers where it supplied some for the log.
            "model_text_shown": 0, "answers_with_log_only_summary": sum(1 for s in submissions if s.get("model_summary"))}  # fmt: skip


def report_complex(questions: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    by_id = {r["question_id"]: r for r in record["results"]}
    rows = []
    for question in questions:
        result = by_id.get(question["id"])
        if result is None:
            continue
        verdict = judge(question, result)
        rows.append({"id": question["id"], "source": question["source"], "type": question["type"], "question": question["question"], **verdict,
                     "cause": None if verdict["outcome"] == "correct" else cause(question, result, verdict), "answer": result["answer"],
                     "requested_outputs": [{"id": o["id"], "kind": o["kind"], "description": o["description"], "covered_by": o["covered_by"]} for o in (result.get("submission") or {}).get("requested_outputs") or []],
                     "tools_used": [s["tool"] for s in result["trace"] if s.get("executed", True)], "repair": result.get("repair"),
                     "llm_calls": result["usage"].get("llm_calls", 0), "tool_calls": sum(1 for s in result["trace"] if s.get("executed", True)), "latency_s": round(result["duration_ms"] / 1000, 1)})  # fmt: skip
    scored = [r["score"] for r in rows if r["score"] is not None]
    return {"suite": "complex", **{k: record[k] for k in ("provider", "model", "commit", "dirty", "run_id")}, "questions": len(rows),
            "outcomes": dict(Counter(r["outcome"] for r in rows)), "mean_score": round(statistics.mean(scored), 3) if scored else None,
            "required_facts": {"found": sum(x["found"] for r in rows for x in r["required"] if x["kind"] == "fact"), "of": sum(1 for r in rows for x in r["required"] if x["kind"] == "fact")},
            "required_unknowns": {"named": sum(x["found"] for r in rows for x in r["required"] if x["kind"] == "unknown"), "of": sum(1 for r in rows for x in r["required"] if x["kind"] == "unknown")},
            "forbidden_facts_cited": sum(len(r["forbidden"]) for r in rows), "grounding": _grounding([by_id[r["id"]] for r in rows]),
            "efficiency": _efficiency([by_id[r["id"]] for r in rows]), "rows": rows}  # fmt: skip


def _slots(facts: list[dict[str, Any]]) -> dict[tuple, set[str]]:
    slots: dict[tuple, set[str]] = {}
    for fact in facts:
        if fact["p"] in FUNCTIONAL:
            slot = (fact["p"], fact.get("s"), (fact.get("q") or {}).get("property"))
            slots.setdefault(slot, set()).add(json.dumps([fact.get("o"), str(fact.get("v")).casefold() if "v" in fact else None]))
    return slots


def _contradictions(fact_sets: list[list[dict[str, Any]]], evidence_sets: list[list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Slots that two answers fill with different values.

    The slot is the object that carries the fact, so two nozzles of one pump are two slots.
    A slot the drawing itself gives several values (seen in one run's tool results) is
    multi-valued, not contradictory.
    """
    multi = {slot for facts in [*fact_sets, *(evidence_sets or [])] for slot, values in _slots(facts).items() if len(values) > 1}
    values: dict[tuple, set[str]] = {}
    for facts in fact_sets:
        for slot, found_values in _slots(facts).items():
            values.setdefault(slot, set()).update(found_values)
    return [{"predicate": p, "subject": s, "property": prop, "values": sorted(v)} for (p, s, prop), v in values.items() if len(v) > 1 and (p, s, prop) not in multi]


def report_consistency(groups: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    by_question: dict[str, list[dict[str, Any]]] = {}
    for result in record["results"]:
        by_question.setdefault(result["question_id"], []).append(result)
    group_rows, causes = [], Counter()
    for group in groups:
        runs = []
        for phrasing in group["phrasings"]:
            for result in sorted(by_question.get(phrasing["id"], []), key=lambda r: r["repeat"]):
                verdict = judge(group, result)  # against the target the whole group shares
                own = judge({**group, "required": phrasing["required"]}, result) if phrasing.get("required") else verdict
                facts, unknowns = answer_facts(result)
                # What the profile compares: required items found, and the unknown categories named.
                profile = None if verdict["profile"] is None else (tuple(verdict["profile"]), tuple(sorted(unknowns)))
                runs.append({"phrasing": phrasing["id"], "repeat": result["repeat"], "question": phrasing["question"], "verdict": verdict, "own": own, "profile": profile, "facts": facts,
                             "resolved": anchors_resolved(group, result), "result": result})  # fmt: skip
        if not runs:
            continue
        profiles = Counter(r["profile"] for r in runs if r["profile"] is not None)
        usual = profiles.most_common(1)[0][0] if profiles else None
        phrasings = []
        for phrasing in group["phrasings"]:
            mine = [r for r in runs if r["phrasing"] == phrasing["id"]]
            if mine:
                phrasings.append({"id": phrasing["id"], "question": phrasing["question"], "repeats": len(mine), "repeat_consistent": len({r["profile"] for r in mine}) == 1 and mine[0]["profile"] is not None,
                                  "recall": [r["verdict"]["score"] for r in mine], "matches_group": all(r["profile"] == usual for r in mine)})  # fmt: skip
        details = []
        for r in runs:
            complete = r["profile"] is not None and all(r["profile"][0])
            reason = None if complete else cause(group, r["result"], r["verdict"])  # a complete answer is never the inconsistent one
            if reason:
                causes[reason] += 1
            details.append({"phrasing": r["phrasing"], "repeat": r["repeat"], "outcome": r["verdict"]["outcome"], "recall": r["verdict"]["score"],
                            "question_outcome": r["own"]["outcome"], "question_score": r["own"]["score"],
                            "missing": [x["item"] for x in r["verdict"]["required"] if not x["found"]], "unknowns": r["verdict"].get("unknown_categories", []),
                            "entities_resolved": r["resolved"], "cited_facts": len(r["facts"]), "cause": reason,
                            "tools_used": [s["tool"] for s in r["result"]["trace"] if s.get("executed", True)], "repair": r["result"].get("repair"),
                            "requested_outputs": [{"id": o["id"], "kind": o["kind"], "covered_by": o["covered_by"]} for o in (r["result"].get("submission") or {}).get("requested_outputs") or []],
                            "latency_s": round(r["result"]["duration_ms"] / 1000, 1), "llm_calls": r["result"]["usage"].get("llm_calls", 0)})  # fmt: skip
        keys = [{fact_key(f) for f in r["facts"]} for r in runs if r["profile"] is not None]
        overlaps = [len(a & b) / len(a | b) for a, b in combinations(keys, 2) if a | b]
        pairs = [(a, b) for a, b in combinations(runs, 2) if a["phrasing"] != b["phrasing"]]
        scores = [r["verdict"]["score"] for r in runs if r["verdict"]["score"] is not None]
        group_rows.append({
            "group": group["id"], "title": group["title"], "based_on_complex": group.get("complex", False), "runs": len(runs),
            "repeat_consistent_phrasings": sum(p["repeat_consistent"] for p in phrasings), "phrasings": len(phrasings),
            "cross_phrasing_consistent": len({r["profile"] for r in runs}) == 1 and usual is not None,
            "cross_phrasing_pair_agreement": round(sum(a["profile"] == b["profile"] and a["profile"] is not None for a, b in pairs) / len(pairs), 3) if pairs else None,
            "contradictions": _contradictions([r["facts"] for r in runs], [evidence_facts(r["result"]) for r in runs]),
            "entity_resolution_consistent": all(r["resolved"] for r in runs),
            "required_fact_recall": round(statistics.mean(scores), 3) if scores else None,
            "jaccard_overlap": round(statistics.mean(overlaps), 3) if overlaps else None,
            "phrasing_rows": phrasings, "run_rows": details,
        })  # fmt: skip
    results = record["results"]
    phrasing_total = sum(g["phrasings"] for g in group_rows)
    return {
        "suite": "consistency", **{k: record[k] for k in ("provider", "model", "commit", "dirty", "run_id", "repeats")}, "groups": len(group_rows), "runs": sum(g["runs"] for g in group_rows),
        "repeat_consistency": {"consistent_phrasings": sum(g["repeat_consistent_phrasings"] for g in group_rows), "of": phrasing_total},
        "cross_phrasing_consistency": {"consistent_groups": sum(g["cross_phrasing_consistent"] for g in group_rows), "of": len(group_rows)},
        "contradictions": sum(len(g["contradictions"]) for g in group_rows),
        "entity_resolution": {"consistent_groups": sum(g["entity_resolution_consistent"] for g in group_rows), "of": len(group_rows)},
        "required_fact_recall": round(statistics.mean([g["required_fact_recall"] for g in group_rows if g["required_fact_recall"] is not None]), 3) if group_rows else None,
        "jaccard_overlap_mean": round(statistics.mean([g["jaccard_overlap"] for g in group_rows if g["jaccard_overlap"] is not None]), 3) if any(g["jaccard_overlap"] is not None for g in group_rows) else None,
        "inconsistency_causes": dict(causes), "grounding": _grounding(results), "efficiency": _efficiency(results), "group_rows": group_rows,
    }  # fmt: skip


def print_complex(report: dict[str, Any]) -> None:
    print(f"\nCOMPLEX  {report['provider']} {report['model']}  commit {report['commit'][:7]}{' (dirty)' if report['dirty'] else ''}")
    for r in report["rows"]:
        print(f"  {r['id']:<5}{r['outcome']:<17}{'' if r['score'] is None else format(r['score'], '.2f'):<6}{r['llm_calls']:>3} calls {r['tool_calls']:>3} tools {r['latency_s']:>6.1f} s  {r['question'][:58]}")
        for x in r["required"]:
            if not x["found"]:
                print(f"         missing: {x['item']}")
        if r["cause"]:
            print(f"         cause: {r['cause']}")
    print(f"  outcomes {report['outcomes']}  mean score {report['mean_score']}  facts {report['required_facts']}  unknowns {report['required_unknowns']}")
    print(f"  grounding {report['grounding']}\n  efficiency {report['efficiency']}")


def print_consistency(report: dict[str, Any]) -> None:
    print(f"\nCONSISTENCY  {report['provider']} {report['model']}  commit {report['commit'][:7]}{' (dirty)' if report['dirty'] else ''}  repeats {report['repeats']}")
    for g in report["group_rows"]:
        print(f"  {g['group']:<4}{g['title'][:34]:<36}repeat {g['repeat_consistent_phrasings']}/{g['phrasings']}  cross-phrasing {'yes' if g['cross_phrasing_consistent'] else 'no '}"
              f"  pairs {g['cross_phrasing_pair_agreement']}  entities {'ok' if g['entity_resolution_consistent'] else 'differ'}  recall {g['required_fact_recall']}  contradictions {len(g['contradictions'])}  jaccard {g['jaccard_overlap']}")  # fmt: skip
        for r in g["run_rows"]:
            if r["cause"]:
                own = "" if r["question_outcome"] == r["outcome"] else f" (own wording: {r['question_outcome']})"
                print(f"         {r['phrasing']} r{r['repeat']}: {r['outcome']}{own}, missing {r['missing']} -> {r['cause']}")
    print(f"  repeat consistency {report['repeat_consistency']}  cross-phrasing {report['cross_phrasing_consistency']}  contradictions {report['contradictions']}  entity resolution {report['entity_resolution']}")
    print(f"  required-fact recall {report['required_fact_recall']}  jaccard (descriptive) {report['jaccard_overlap_mean']}  causes {report['inconsistency_causes']}")
    print(f"  grounding {report['grounding']}\n  efficiency {report['efficiency']}")


def phrasing_items(groups: list[dict[str, Any]], only: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    return [{"id": p["id"], "question": p["question"], "group": g["id"]} for g in groups for p in g["phrasings"] if only is None or p["id"] in only.get(g["id"], [])]


def score_all(root: Path) -> None:
    questions, groups = json.loads(COMPLEX.read_text())["questions"], json.loads(GROUPS.read_text())["groups"]
    for run_file in sorted(root.glob("*/*/run.json")):
        record = json.loads(run_file.read_text())
        report = report_complex(questions, record) if record["suite"] == "complex" else report_consistency(groups, record)
        (run_file.parent / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        (print_complex if record["suite"] == "complex" else print_consistency)(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", choices=("complex", "consistency", "smoke"), help="ask the questions with the configured provider and model, then score")
    parser.add_argument("--repeats", type=int, default=3, help="times each phrasing is asked (consistency only)")
    parser.add_argument("--only", help="comma-separated question or group ids")
    parser.add_argument("--pause", type=float, default=1.0)
    args = parser.parse_args()
    questions, groups = json.loads(COMPLEX.read_text())["questions"], json.loads(GROUPS.read_text())["groups"]
    only = set(args.only.split(",")) if args.only else None
    root = HERE / ("smoke" if args.run == "smoke" else "runs")
    if args.run == "smoke":
        run("complex", [q for q in questions if q["id"] in SMOKE["complex"]], 1, root, args.pause)
        run("consistency", phrasing_items(groups, SMOKE["groups"]), 1, root, args.pause)
    elif args.run == "complex":
        run("complex", [q for q in questions if only is None or q["id"] in only], 1, root, args.pause)
    elif args.run == "consistency":
        run("consistency", [i for i in phrasing_items(groups) if only is None or i["group"] in only], args.repeats, root, args.pause)
    for folder in (HERE / "smoke", HERE / "runs"):  # the dated smoke-N folders are earlier diagnostics and keep their own reports
        score_all(folder)


if __name__ == "__main__":
    main()
