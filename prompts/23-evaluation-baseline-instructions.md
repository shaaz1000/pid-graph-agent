Let the current 15-question evaluation finish. Do NOT interrupt or restart it.

Do not modify code, prompts, model settings, graph behaviour, or evaluation expectations while the run is in progress. We need this to remain a clean baseline.

For every question capture:

- pass/fail
- grounded status
- final answer
- tool calls
- LLM call count
- graph tool call count
- total latency
- latency per LLM call if available
- finish_reason
- completion tokens
- reasoning tokens where available
- rewrites/retries
- failure category if applicable

The first question taking 109 seconds confirms that latency needs to be treated separately from correctness.

While the evaluation runs, you may tidy documentation/audit material, but do not make behavioural changes.

When all 15 complete, first give me the UNMODIFIED baseline results.

Then calculate:

- score / 15
- grounded / 15
- unsupported claims
- median latency
- mean latency
- p95 latency
- fastest question
- slowest question
- average LLM calls/question
- total LLM calls
- percentage of time attributable to LLM/provider calls if measurable
- number of rewrites
- number of truncations
- number of provider/timeouts

Also classify every failure into:
A planning
B entity resolution
C graph retrieval
D graph abstraction/data
E flow-direction ambiguity
F missing DEXPI information
G answer synthesis
H grounding validator
I evaluation expectation

Do not fix individual failures yet.

After showing me the baseline, identify the smallest GENERAL optimization that would reduce latency without weakening unseen-question generalization or grounding.

In particular, investigate whether final answer synthesis is consuming a large fraction of the latency and whether:
1. documented low-reasoning synthesis, or
2. deterministic rendering of simple structured graph results

can remove unnecessary model work.

Do not add question-specific shortcuts or templates.

Most importantly: DO NOT rerun the full 15-question evaluation automatically after making any optimization.

Show me the baseline first and wait.
