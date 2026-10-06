# Follow-up Exercise

Complex operational questions and consistency under rephrasing, on the same C01 P&ID.
The exercise as received is in [prompts/29](../prompts/29-followup-exercise-from-intuigence.md);
the instructions that shaped this round are prompts 30 to 35.

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
in separate commits (`cdec2a8` and the one after it): a status is now stated in fixed
application wording, and a value is shown only if it occurs in the user's question as whole
words or is canonical graph data. The hardened code did not produce the recorded results.

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

**Next step for production.** Reduce planner freedom with a typed planning or capability
layer, use composite deterministic graph analyses for the common multi-hop operations, and
keep the structured answer contract.

## Reproduce

```bash
uv run pytest                                              # 784 deterministic tests, no key
uv run python evals/followup/followup.py                   # re-score the saved runs, no key
uv run python evals/followup/followup.py --run complex     # ask the 27 complex questions
uv run python evals/followup/followup.py --run consistency --repeats 3
```

Questions and gold: [complex/questions.json](../evals/followup/complex/questions.json),
[consistency/groups.json](../evals/followup/consistency/groups.json). Every gold fact is
re-derived from the graph by `tests/test_followup.py`. Runs, reports and transcripts with the
tool trace of every question: [evals/followup/runs/](../evals/followup/runs/).

## Time spent

About four and a half hours of elapsed time from receiving the follow-up to this report,
measured from the working session: roughly 1 h 45 min of that was the unattended full
evaluation and about 45 min the smaller diagnostic runs. An AI coding assistant was used
throughout, directed by the six instructions in `prompts/30` to `prompts/35`.
