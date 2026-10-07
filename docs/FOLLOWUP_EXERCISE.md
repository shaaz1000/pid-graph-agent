# Follow-up Exercise

Complex questions and consistency under rephrasing, on the same C01 P&ID. This is the short
note; tables, causes and method are in [FOLLOWUP_DETAILS.md](FOLLOWUP_DETAILS.md).

## What changed

**Structured answers replace prose validation.** The model no longer writes an answer that
code then reads back with patterns. It first records what the question asks for (request
decomposition into outputs q1, q2, ...), calls generic graph tools, and finishes with a
structured submission: evidence ids of *direct facts* (read from the drawing), of *derived
facts* (computed by a graph operation, with the operation and its inputs recorded) and *typed
unknowns* (a closure order, a pressure response, an off-page destination). The application
checks that every id exists and every requested output is covered, then writes the answer
itself. No model-authored factual prose is shown.

**Generic multi-step graph analyses.** New operations, each a general graph concept with no
link to any question: the isolation boundary of an item, a whole instrumentation chain, a line
as runs between junctions, reachability and routes with items treated as closed, and all
routes between two items. "If this valve closes" is answered by graph reachability with that
item blocked, not by reasoning about flow.

**Regex.** The sentence-level validator (relation words, hedges, negation) is not used on this
path. Regex remains only for lexical and protocol work, and in the earlier prose contract,
kept so the earlier recorded runs stay reproducible.

## What was tested

27 complex questions (the 15 provided and 12 of our own) and 10 rephrasing groups (the 4
provided and 6 of our own; 41 phrasings), each phrasing asked 3 times as an independent turn:
150 scheduled runs, 149 answered, 1 provider failure. Model: NVIDIA-hosted Nemotron 3 Super,
an open-weight model released under the NVIDIA Nemotron Open Model License; no paid inference
was used. Two answers agree when they contain the same required facts, compared as graph facts
and never as text. The check is automated (`evals/followup/followup.py`) and classifies every
miss by cause.

## Results

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
- **Directional versus direction-agnostic routes.** A route query that ignores flow direction
  can return a path that is valid in the graph but is not a process-flow route, for example
  T4750 -> SV 104.01 -> P4712, backwards through the relief valve. Such a row is graph
  connectivity and must not be read as process flow; the agent can still choose it when asked
  whether a route "remains".
- **Licence.** Nemotron is open-weight, not OSI open source. Provider and model are
  configuration.

After the evaluation, a security review found that a status message could repeat model-chosen
input. No evaluated answer was affected; the rendering was hardened in separate commits. A
frozen holdout on the hardened branch found no regression and reproduced the route limitation.

## Time

About five hours of working time, of which roughly three were unattended model runs. That is
more than the four hours suggested.

## Where things are

- Detailed results and method: [FOLLOWUP_DETAILS.md](FOLLOWUP_DETAILS.md)
- Questions, gold, runs, reports and transcripts with the tool trace of every answer:
  [evals/followup/](../evals/followup/) (`runs/` is the official evaluation, on commit `87953f4`)
- Post-evaluation holdout: [evals/followup/holdout/](../evals/followup/holdout/README.md)
- The exercise and the instructions for this round: [prompts/](../prompts/) 29 to 37
