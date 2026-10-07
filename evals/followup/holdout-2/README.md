# POST-EVALUATION ARCHITECTURE HOLDOUT 2

This is **not** part of the official follow-up evaluation (the 150 runs under `../runs/`,
made on commit `87953f4`), and it is separate from the first holdout under `../holdout/`.
It is a second small check, made after the post-evaluation architecture pass (capability
declarations, completion of composite results, explicit route semantics), on fresh questions.

- Commit evaluated: `1abcc01dda344c0416d139bfe68a8ad8132e0aa9`, clean working tree
  (`"dirty": false` in both `run.json` files).
- Model: NVIDIA-hosted `nvidia/nemotron-3-super-120b-a12b` (open-weight, NVIDIA Nemotron Open
  Model License). No paid inference.
- Questions and gold were created and committed (in `1abcc01`) before inference. No code,
  prompt or gold change was made between seeing a result and the recorded run; the results
  below are the first and only run. Nothing was rescored.
- Two fixes were made **after** this run and were **not** re-evaluated with a model: absence
  facts that state their filter and bound, and completion and flow safety derived from the
  cited operation instead of the model's label (see "What the run exposed"). The numbers
  below describe commit `1abcc01`, not the later code.

## What was run

- 8 fresh complex questions, one run each ([questions.json](questions.json)).
- 4 fresh rephrasing groups, 4 phrasings each, 2 independent repeats each
  ([groups.json](groups.json)).
- 40 scheduled inference runs, 40 answered, 0 provider failures, 0 withheld.
- 254 model calls (39 + 215), 171 tool calls, about 1.67 million tokens.

Gold was derived from the graph by [build_holdout.py](build_holdout.py), which rejects any
fact pattern that no graph operation produces. Scoring uses the unchanged follow-up evaluator
([run_holdout.py](run_holdout.py)).

## Complex holdout (8 questions)

| | |
|---|---|
| Correct / partial / incorrect / withheld | 5 / 3 / 0 / 0 |
| Mean score | 0.87 |
| Required facts found | 25 of 28 |
| Contradictions | 0 |
| Unsupported facts | 0 |

Eight questions are too few to claim an improvement over the official run.

## Paraphrase holdout (4 groups, 16 phrasings, 2 repeats, 32 runs)

| | |
|---|---|
| Repeat-consistent phrasings | 11 of 16 |
| Groups fully consistent across phrasings | 0 of 4 |
| Required-fact recall | 0.72 |
| Entity resolution consistent | 4 of 4 groups |
| Contradictions | 0 |

| Group | Repeat-consistent phrasings | Pair agreement across phrasings | Required-fact recall | Runs using the same key operation |
|---|---|---|---|---|
| KG1 boundary of a fitting | 3 of 4 | 0.75 | 0.875 | 7 of 8 |
| KG2 flow route versus piping link | 3 of 4 | 0.167 | 0.562 | 6 of 8 |
| KG3 a loop entered from its valve | 4 of 4 | 0.5 | 0.938 | 8 of 8 |
| KG4 what remains downstream with a valve closed | 1 of 4 | 0.333 | 0.5 | 7 of 8 |

The agent is still not consistent under rephrasing. Planning and the kind the model assigns
to a requested output vary between phrasings and between repeats.

## Safety checks over the 40 answers

| Check | Count |
|---|---|
| Process-route semantic errors (a direction-agnostic route given for a flow question) | 0 |
| Contradictions between answers | 0 |
| Rendered facts outside the tool evidence | 0 |
| Model-authored prose shown | 0 |
| Rows added by the application to complete a composite result | 27 |
| Facts retrieved but left out of the answer | 4 |

The backwards route through the relief valve that the first holdout exposed (HG2) did not
appear as an answer to a flow question in any run.

## What the run exposed

- **The model's label was the trust boundary.** Completion of a composite result and the
  flow-semantics check both followed the kind the model gave a requested output. In KG3 some
  runs labelled a control-loop output as items or property, so the loop was not completed and
  the fail action was left out twice. One KG1 run labelled a boundary question as adjacency
  and answered from adjacency rows. Fixed after this run: completion and what a route proves
  are now read from the cited operation and its result. A wrong label that makes the model
  call a different operation is planner variance and remains.
- **An empty traversal was citable without its conditions.** The "nothing reached" fact did
  not state the type filter or the depth bound. No run here was affected (no empty traversal
  had a depth limit). Fixed after this run.
- **A known limit of the gold.** Where the correct answer is that an item is absent from a
  list (for example that a downstream reach does not contain a given pump), there is no
  positive fact to match, so recall for KG2 and KG4 understates some runs. The gold was not
  changed.

## Files

`runs/<model>/complex/` and `runs/<model>/consistency/`: `run.json` (full traces and tool
results), `report.json`, and a transcript per run.
