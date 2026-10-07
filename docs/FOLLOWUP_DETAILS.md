# Follow-up Exercise: detailed results

The one-page note is [FOLLOWUP_EXERCISE.md](FOLLOWUP_EXERCISE.md). This file holds the detail
behind it: the design, the full result tables, causes, and the post-evaluation checks.
The exercise as received is in [prompts/29](../prompts/29-followup-exercise-from-intuigence.md);
the instructions that shaped this round are prompts 30 to 37.

## What was tested

The follow-up asked for four things: more complex operational P&ID questions, the same
question rephrased with the facts staying the same, an automated consistency measurement, and
less reliance on regex for semantic grounding.

**What changed.** The follow-up path no longer has the model write an answer that code then
reads back with patterns:

```
question
  -> structured request decomposition      what is asked, as outputs q1, q2, ...
  -> generic graph tools                   the model chooses; no question -> tool mapping
  -> direct facts / derived facts / typed unknowns
  -> schema validation                     every id exists; every requested output is covered
  -> application-rendered answer
```

- **Graph operations for multi-step questions**, each a general graph concept: the isolation
  boundary of an item, a whole instrumentation chain, a line as runs between junctions,
  reachability and routes with items treated as closed, all routes between two items, and
  listing with attributes and a property filter. They run on all 35 official DEXPI examples.
- **Structured answers.** The model finishes with `submit_answer`: evidence ids of *direct
  facts* (read from the drawing), of *derived facts* (computed by a graph operation, with the
  operation and its inputs recorded), and *typed unknowns* (a closure order, a pressure
  response, an off-page destination). The application writes the answer from those rows and
  from one fixed sentence per unknown category. No model-authored factual prose is shown in
  the scored path.
- **Regex.** The sentence-level validator (relation words, hedges, negation, claim extraction
  from prose) is not used on this path. Regex remains where it is lexical or protocol work:
  identifier normalisation in the resolver, citation parsing, and the earlier prose contract,
  which is kept only so the recorded C01 and cross-P&ID runs stay reproducible.
- **Where the drawing is silent, the answer says so.** A hypothetical ("if this valve closes")
  is answered by graph reachability with that item blocked, not by reasoning about flow.
  Closure order, pressure behaviour and relief adequacy are returned as unknowns, never invented.

**How two answers are judged to agree.** Never by text. An answer is the set of canonical
facts of the rows it cites, plus the categories of its unknowns. Each group of phrasings has
a set of required facts derived from the graph. Two runs agree when they found the same
required facts and named the same unknowns; extra correct facts do not count as disagreement.
A contradiction is the same object and property with different values.

## Results

Model: `nvidia/nemotron-3-super-120b-a12b`, an open-weight model released under the NVIDIA
Nemotron Open Model License. Every question was asked as an independent turn. Run on commit
`87953f4` with a clean tree; nothing was re-asked for a better result.

### Complex questions (27, one run each)

| | Questions | Correct | Partial | Incorrect | Withheld | Mean score |
|---|---|---|---|---|---|---|
| Provided C1 to C15 | 15 | 5 | 9 | 0 | 1 | 0.67 |
| Our own | 12 | 6 | 2 | 3 | 1 | 0.60 |
| **All** | **27** | **11** | **11** | **3** | **2** | **0.64** |

Required facts found: 82 of 128. Required unknowns named: 4 of 8. Causes of the 16 misses:
incomplete traversal 6, planner/tool choice 6, grounding rejection 2, answer synthesis 1,
entity resolution 1.

This is not a high score. The complex suite exposed planning depth and tool-selection
variance that the earlier, simpler evaluation did not show.

### Consistency (10 groups, 41 phrasings, 3 repeats, 123 runs)

Three different things, reported separately:

| | Result |
|---|---|
| 1. Repeat consistency: the 3 runs of one phrasing agree | 22 of 41 phrasings |
| 2. Paraphrase consistency: every run of a group agrees | 1 of 10 groups |
| 3. Semantic correctness: required-fact recall | 0.70 |
| Entity resolution consistent | 7 of 10 groups |
| Contradictions | 0 |
| Jaccard overlap of cited facts (descriptive only) | 0.44 |

Per run: 58 correct, 43 partial, 18 incorrect, 3 withheld, 1 provider failure (kept as
recorded). Provided groups R1 to R4: recall 0.56, pair agreement 0.22. Our own groups: recall
0.79, pair agreement 0.52.

| Group | Repeat-consistent phrasings | Pair agreement | Recall |
|---|---|---|---|
| R1 isolating a pump | 1 of 5 | 0.43 | 0.87 |
| R2 fail-position impact | 1 of 4 | 0.11 | 0.39 |
| R3 loop mapping | 1 of 4 | 0.06 | 0.46 |
| R4 blocked-in | 3 of 4 | 0.28 | 0.53 |
| G1 isolating a heat exchanger | 2 of 4 | 0.39 | 0.74 |
| G2 reach with one valve closed | 0 of 4 | 0.15 | 0.23 |
| G3 temperature loop | 3 of 4 | 0.67 | 0.96 |
| G4 an item by tag, type, context, shorthand | 4 of 4 | 1.00 | 1.00 |
| G5 a route with lines and sizes | 3 of 4 | 0.39 | 0.90 |
| G6 a relief device | 4 of 4 | 0.50 | 0.92 |

### The main finding

The agent is not consistent under rephrasing. The structured grounding path remained safe and
contradiction-free, but the planner was not sufficiently stable under complex multi-step
phrasing. Most inconsistencies came from retrieving or citing different subsets of valid graph
facts, rather than from contradictory facts.

Causes of the 65 incomplete consistency runs: answer synthesis (retrieved but not cited) 27,
planner/tool choice 18, incomplete traversal 11, entity resolution 5, grounding rejection 3,
provider 1. Recurring examples:

- R1 often found all four boundary valves but omitted the relief-line fact.
- R2 and G2 often did not test reachability after closing a valve.
- R3 often stopped at the controller's immediate links.

### Grounding and trust

- 144 structured answers from 149 answered runs; 5 withheld.
- No rendered answer cited a fact outside its tool evidence, and no model-authored factual
  prose was shown. The answer contract enforces this structurally: a cited id that does not
  exist is rejected, and the answer text is written by the application.
- 0 contradictions.
- 300 requested outputs, all accounted for: 268 covered by facts, 42 by typed unknowns
  (some by both).
- 18 rejected submissions, handled by the normal retry or the repair; 6 final repairs
  attempted, 6 succeeded.

### Infrastructure

1,013 model calls, 698 graph tool calls, 6.43M tokens, 1 h 45 min wall time, 1 provider
failure. Latency per question: complex median 43.9 s, mean 54.7 s; consistency median 24.5 s,
mean 30.3 s.

Evaluation used the existing NVIDIA-hosted Nemotron 3 Super endpoint. No paid inference
service or provider upgrade was required. Provider and model selection are configuration:
`openai/gpt-oss-20b` (Apache-2.0) was tried on the same endpoint and was weaker on tool choice;
`openai/gpt-oss-120b` (Apache-2.0) on Groq did well on a partial smoke but its free daily quota
could not carry the evaluation. Those runs are kept as diagnostics
([evals/followup/SMOKE_RUNS.md](../evals/followup/SMOKE_RUNS.md)).

### Security note

The follow-up evaluation was run on commit 87953f4. A post-evaluation security review
identified a status-message provenance issue: a tool's status message can repeat its input,
which the model chooses, so a cited status row could print model-chosen text. No evaluated
answer contained injected model prose (5 status rows were cited; 2 repeated an input that was
not in the question, both graph ids or a type name). The rendering path was hardened afterward
in separate commits (`cdec2a8` and the two after it): a status is now stated in fixed
application wording, and a value is shown only if it occurs in the user's question as whole
words or is canonical graph data, and then only in that canonical spelling, never as the
model wrote it. The hardened code did not produce the recorded results.

## Limitations

- Planner and tool selection is the dominant limitation.
- Multi-hop traversals frequently terminate too early (the 8-step budget is reached).
- Answer construction sometimes omits facts that were retrieved.
- Entity resolution is not fully stable under indirect or property-based phrasing.
- Unknown / not-in-drawing coverage is incomplete: 4 of 8 required unknowns were named.
- Hosted model and provider variance exists; the same phrasing gave different results in 19
  of 41 cases.
- The evaluation is the reference C01 follow-up set with gold we derived from the graph, not
  a blind benchmark written by a process engineer.
- Nemotron is open-weight rather than OSI open source.
- "Map all connections for X" (R3a) can be read as the controller's own links. That reading is
  scored correct for the question, and still counts against the group's consistency.
- The agent keeps no conversation history, so the optional successive-turn test was not run.
- **Topological reachability is not process reachability.** A route query that ignores flow
  direction (`direction=any`) can return a path that is valid in the graph but is not a
  process-flow route. Observed: with the tank's outlet valve treated as closed, the route
  T4750 -> SV 104.01 -> piping -> P4712 exists in the graph, but it runs backwards through the
  relief valve into the pump's discharge. The row is labelled "direction any" and is correct
  as connectivity; it must not be read as "the tank can still feed the pump". The agent can
  still choose this operation when a question asks whether a route "remains". This affected
  H5 and HG2 in the first holdout below and is related to the miss on C7. *Since then:* such a
  route is marked topological, worded as connectivity, and blocked from satisfying a
  process-flow output (see "Post-evaluation architecture hardening").

**Next step for production.** Reduce planner freedom further. A capability layer and
deterministic completion of composite analyses now exist (see "Post-evaluation architecture
hardening"), but the choice of operation is still the model's and still varies.

## Post-evaluation holdout / sanity check

Not part of the official 150-run evaluation. After the security hardening, a separate holdout
was run on the hardened branch (commit `fd4dfe8`) to see whether the final code still answers
fresh questions. The holdout was created and frozen before inference. No code, prompt or gold
changes were made after results were observed. Details:
[evals/followup/holdout/README.md](../evals/followup/holdout/README.md).

- 8 new complex questions, one run each: 5 correct, 2 partial, 1 incorrect, mean 0.78;
  required facts 18 of 22, required unknowns 1 of 1; 0 contradictions, 0 unsupported facts.
- 3 new rephrasing groups, 4 phrasings each, 2 repeats (24 runs, 23 answered, 1 provider
  timeout): 10 of 12 phrasings repeat-consistent on required facts. HG1 was fully consistent
  on required facts; HG3 in 7 of 8 answered runs.
- HG2 exposed a semantic weakness: direction-agnostic connectivity can be stable across
  paraphrases while still answering the wrong process-level question. The evaluator's raw
  consistency figure for HG2 is high and must not be read as success; its required-fact
  recall is 0.00 (see the limitation above).
- No grounding or security regression: 0 model-authored prose in rendered answers, 0 cited
  ids missing from tool results, 0 model-controlled tool-input text in rendered output.

## Post-evaluation architecture hardening

Made after the official evaluation and after the first holdout. The official 150-run figures
above are unchanged and historical; none of this was re-run on that set.

The post-evaluation architecture hardening prevents direction-agnostic connectivity from
satisfying process-flow outputs and completes composite analysis results deterministically
from operation semantics. A second frozen holdout found 0 process-route semantic errors, 0
contradictions and 0 unsupported facts, while planner/kind-selection variance remained.

- **Capability declarations and constrained planning.** `capabilities.py` declares, as data,
  which operations can answer each kind of requested output (a boundary by
  `isolation_boundary`, a signal chain by `trace_instrumentation`, a line structure by
  `trace_line`, flow reachability by `traverse` or `find_path` along the drawn flow). After
  the decomposition the model is told which operations fit each output. Outputs a drawing
  does not contain (procedures, behaviour) must be named as unknowns.
- **Topological versus drawn-flow route semantics.** `traverse` and `find_path` mark every
  result `drawn_flow` (direction downstream or upstream) or `topological` (direction any or
  both). A topological route also reports how many pipes it follows against the drawn flow
  and which check or relief devices it passes against their flow direction. It is rendered
  as "connected by piping when flow direction is ignored", never as a route.
- **Deterministic composite completion based on operation semantics.** Citing any row of an
  isolation boundary, an instrumentation chain, a line trace or a route set makes the
  application add the core rows of that same result: boundary valves, unisolated connections
  and relief rows; measurement point, signal chain, final element, fail action and line
  context; the runs of a line; every route found. Rows of other results, and the item and
  property rows of the same result, are added only if cited.
- **The trust boundary no longer depends on the model-assigned kind.** In the second holdout
  completion and the flow check still followed the kind the model gave an output, and a wrong
  label switched them off. Now the kind is used for planning and can only tighten the check.
  What the evidence for an output establishes is computed from the operation and the route
  semantics of its result: a topological route gives connectivity and never flow
  reachability under any label, and each answered output records this row by row
  (`route_evidence`). Planning and kind assignment remain variable: a wrong label can still
  lead the model to call a different operation, and the application cannot know that a
  question was about flow if neither the label nor the evidence says so. In that case the
  answer still states connectivity only.
- **Citable completed empty traversal facts.** An empty traversal gives the fact
  `reaches_nothing` only when the search ran to the end of the drawn piping. The fact and its
  fixed wording carry the start, the direction, the items treated as closed, the type filter
  and the depth bound, and name any off-page connector the searched piping ends at. A search cut off at its depth limit, told to stop at certain types, or
  filtered by a type the graph does not have gives `found_nothing_within_search_limits`,
  worded as not showing that nothing lies beyond. Without a type filter the statement is
  about every kind of item and is not narrowed to equipment.

## Second post-evaluation holdout

Not part of the official evaluation. Run on commit `1abcc01` (clean tree) after the capability
and route-semantics pass, on questions and gold committed before inference; recorded as
produced, nothing rescored. Details:
[evals/followup/holdout-2/README.md](../evals/followup/holdout-2/README.md).

- 8 new complex questions, one run each: 5 correct, 3 partial, 0 incorrect, 0 withheld; mean
  0.87; required facts 25 of 28.
- 4 new rephrasing groups, 4 phrasings each, 2 repeats (32 runs, all answered): 11 of 16
  phrasings repeat-consistent, 0 of 4 groups fully consistent across phrasings, required-fact
  recall 0.72, entity resolution consistent in 4 of 4 groups.
- 0 process-route semantic errors, 0 contradictions, 0 unsupported facts, 0 model-authored
  prose, 0 provider failures. The application added 27 rows to complete composite results.
- Consistency did not improve in any way this small set can show. The misses were planner and
  kind-selection variance: for example, runs that labelled a control-loop output as items
  were not completed and two left out the fail action.
- The two fixes that came after this run (operation semantics as the trust boundary; absence
  facts with their filter and bound) were verified with deterministic tests only. No model
  run was made after them.

## Reproduce

```bash
uv run pytest                                              # 861 deterministic tests, no key
uv run python evals/followup/holdout/run_holdout.py        # re-score the holdout, no key
uv run python evals/followup/holdout-2/run_holdout.py      # re-score the second holdout, no key
uv run python evals/followup/followup.py                   # re-score the saved runs, no key
uv run python evals/followup/followup.py --run complex     # ask the 27 complex questions
uv run python evals/followup/followup.py --run consistency --repeats 3
```

Questions and gold: [complex/questions.json](../evals/followup/complex/questions.json),
[consistency/groups.json](../evals/followup/consistency/groups.json). Every gold fact is
re-derived from the graph by `tests/test_followup.py`. Runs, reports and transcripts with the
tool trace of every question: [evals/followup/runs/](../evals/followup/runs/).

## Time spent

About five hours of working time from receiving the follow-up to the final holdout, measured
from the working session and excluding an overnight idle gap. Roughly three of those hours
were unattended model runs (the 150-run evaluation 1 h 45 min, the diagnostic smoke runs about
45 min, the holdout about 30 min). That is more than the four hours suggested. An AI coding
assistant was used throughout, directed by the instructions in `prompts/30` to `prompts/37`.
The later architecture hardening and second holdout (`prompts/39`, `prompts/40`) are not
included in that figure.
