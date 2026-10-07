# Follow-up Exercise

Complex questions and consistency under rephrasing, on the same C01 P&ID. This is the short
note; tables, causes and method are in [FOLLOWUP_DETAILS.md](FOLLOWUP_DETAILS.md).

## What changed

**Structured answers replace prose validation.** The model no longer writes an answer that
code then reads back with patterns. It records what the question asks for, calls generic graph
tools, and submits evidence ids: *direct facts* read from the drawing, *derived facts* computed
by a graph operation, and *typed unknowns* (a closure order, a pressure response, an off-page
destination). The application checks every id and every requested output, then writes the
answer itself. No model-authored factual prose is shown.

**Generic multi-step graph analyses.** New operations, none tied to any question: the
isolation boundary of an item, a whole instrumentation chain, a line as runs between
junctions, and reachability and routes with items treated as closed. "If this valve closes" is
answered by graph reachability with that item blocked.

**Regex.** The sentence-level validator is not used on this path. Regex remains only for
lexical and protocol work, and in the earlier prose contract, kept so the earlier recorded
runs stay reproducible.

## What was tested

27 complex questions (the 15 provided and 12 of our own) and 10 rephrasing groups (the 4
provided and 6 of our own; 41 phrasings), each phrasing asked 3 times as an independent turn:
150 scheduled runs, 149 answered, 1 provider failure. Model: NVIDIA-hosted Nemotron 3 Super,
an open-weight model released under the NVIDIA Nemotron Open Model License; no paid inference
was used. Two answers agree when they contain the same required facts, compared as graph facts
and never as text. The check is automated and classifies every miss by cause.

## Results

Official evaluation, commit `87953f4`.

| Complex questions (27) | |
|---|---|
| Mean score | 0.64 |
| Correct / partial / incorrect / withheld | 11 / 11 / 3 / 2 |

| Consistency (41 phrasings, 3 repeats) | |
|---|---|
| Repeat-consistent phrasings | 22 of 41 |
| Groups fully consistent across phrasings | 1 of 10 |
| Required-fact recall | 0.70 |
| Contradictions between answers | 0 |
| Rendered facts outside the tool evidence | 0 |
| Model-authored factual prose shown | 0 |

The agent is not consistent under rephrasing. The structured path stayed safe and free of
contradictions, but answers differ in which valid facts they retrieve and cite.

## What still fails

- **Planner and tool selection vary.** The same question can lead to different operations.
- **Multi-hop questions stop early**, at the step limit or one lookup short.
- **Retrieved facts are sometimes left out** of the final structured answer.
- **Licence.** Nemotron is open-weight, not OSI open source. Provider and model are
  configuration.

## After the evaluation

The figures above are historical; later changes were not re-run on that set. A security
review led to hardened status messages (no evaluated answer was affected), and a first frozen
holdout exposed a route that ignored flow direction, backwards through a relief valve, being
given for a flow question.

The post-evaluation architecture hardening prevents direction-agnostic connectivity from
satisfying process-flow outputs and completes composite analysis results deterministically
from operation semantics. A second frozen holdout found 0 process-route semantic errors, 0
contradictions and 0 unsupported facts, while planner/kind-selection variance remained. It
does not show that consistency improved.

## Time

About five hours of working time, of which roughly three were unattended model runs. That is
more than the four hours suggested.

## Where things are

- Detailed results, method and the hardening: [FOLLOWUP_DETAILS.md](FOLLOWUP_DETAILS.md)
- Questions, gold, runs, reports and transcripts: [evals/followup/](../evals/followup/)
- Holdouts: [first](../evals/followup/holdout/README.md),
  [second](../evals/followup/holdout-2/README.md)
- Instructions for this round: [prompts/](../prompts/) 29 to 40
