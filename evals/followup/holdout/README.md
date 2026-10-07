# POST-EVALUATION HOLDOUT / SANITY CHECK

This is **not** part of the official follow-up evaluation (the 150 runs under `../runs/`,
made on commit `87953f4`). It is a small check made afterwards, on the hardened final branch,
to see whether the final code still answers fresh questions.

- Hardened commit evaluated: `fd4dfe8022b45fe7833f7ff517a0533b217913d9`
- Model: NVIDIA-hosted `nvidia/nemotron-3-super-120b-a12b` (open-weight, NVIDIA Nemotron Open
  Model License). No paid inference.
- The holdout was created and frozen before inference. No code, prompt or gold changes were
  made after results were observed.
- None of the 20 questions, nor any six-word run of one, appears elsewhere in the repository.

## What was run

- 8 fresh complex questions, one run each ([questions.json](questions.json)).
- 3 fresh rephrasing groups built on three of them, 4 phrasings each (an exact identifier, a
  type description, a property or context description, terse operator wording), 2 independent
  repeats each ([groups.json](groups.json)).
- 32 scheduled inference runs, 31 answered, 1 provider timeout (HG1d, second repeat), kept as
  recorded.

Gold was derived from the graph by [build_holdout.py](build_holdout.py), which rejects any
fact pattern that no graph operation produces. Scoring uses the unchanged follow-up evaluator
([run_holdout.py](run_holdout.py)).

## Complex holdout

| | |
|---|---|
| Correct / partial / incorrect / withheld | 5 / 2 / 1 / 0 |
| Mean score | 0.78 |
| Required facts found | 18 of 22 |
| Required unknowns named | 1 of 1 |
| Contradictions | 0 |
| Unsupported facts | 0 |

With eight questions this shows that nothing regressed; it does not show an improvement over
the official run.

## Paraphrase holdout

Counted on required facts (the evaluator's own profile also compares which unknowns were named):

| Group | Answered | Repeat-consistent phrasings | Runs with every required fact |
|---|---|---|---|
| HG1 valves around a fitting | 7 of 8 | 3 of 4 | 7 of 7 |
| HG2 a route with one valve closed | 8 of 8 | 4 of 4 | 0 of 8 |
| HG3 an indication and where it is tapped | 8 of 8 | 3 of 4 | 7 of 8 |

- 10 of 12 phrasings were repeat-consistent on required facts. The two exceptions are HG1d
  (one repeat lost to the provider timeout) and HG3a (one run left out one fact).
- HG1 was fully consistent on required facts across all four reference styles.
- HG3 was consistent in 7 of 8 answered runs.
- **HG2 must not be read as a success.** HG2 exposed a semantic weakness: direction-agnostic
  connectivity can be stable across paraphrases while still answering the wrong process-level
  question. Asked whether a drawn route remains from T4750 to P4712 with the tank's outlet
  valve closed, four runs cited the route T4750 -> SV 104.01 -> piping -> P4712. That route
  exists in the graph when direction is ignored, but it runs backwards through the relief
  valve into the pump's discharge. Two runs correctly found nothing downstream of the tank
  and cited that status; the gold cannot credit them, because an empty traversal produces no
  fact to match. Two runs cited neither. The evaluator's raw consistency figure for HG2 is
  therefore misleading in both directions, and its recall of 0.00 overstates the failure for
  two runs. The graph is not wrong here: the distinction is between undirected, topological
  reachability and directional, process reachability.

## Security and provenance audit of the 31 answers

| Check | Count |
|---|---|
| Model-authored prose in a rendered answer | 0 |
| Cited ids missing from the tool results | 0 |
| Model-controlled tool-input text in rendered output | 0 |
| Status rows cited | 3, all in the application's fixed wording with canonical graph names |

## Files

`runs/<model>/complex/` and `runs/<model>/consistency/`: `run.json` (full traces and tool
results), `report.json`, and a transcript per run.
