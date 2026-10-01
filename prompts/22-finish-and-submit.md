We need to stop expanding the scope.

NVIDIA/Nemotron latency is now materially affecting development time.

Do not spend significant additional time optimizing NVIDIA infrastructure.

Our priority is to finish the take-home cleanly.

First determine how many LLM calls are currently required for a typical successful question.

Then identify which calls are genuinely necessary.

Architectural rule:

USE THE LLM WHERE REASONING IS REQUIRED.
DO NOT USE THE LLM TO REFORMAT FACTS THE GRAPH ALREADY RETURNED.

For simple deterministic graph results, prefer application-side answer formatting.

Examples:

entity lookup
property lookup
direct connection
enumeration
simple traversal result

should be capable of being rendered directly from structured GraphService results and evidence.

Do not make another expensive LLM call merely to convert:

{
  "tag": "P4711",
  "destination": "H1007",
  "diameter": "DN80"
}

into an English sentence.

For complex multi-result explanations where natural-language synthesis adds value, retain LLM synthesis.

Keep evidence references and grounding validation.

Measure before/after:

- LLM calls/question
- graph tool calls/question
- end-to-end latency
- correctness
- grounding
- unsupported claims

Do NOT create question-specific templates.

Formatting must operate on generic structured result types.

Also investigate the documented low-reasoning option for FINAL SYNTHESIS ONLY.

Do not reduce reasoning for planning/tool selection because Nemotron's planning performance is currently one of its strengths.

Timebox this optimization to 30 minutes maximum.

After that:

1. make NVIDIA/Nemotron 3 Super the configured submission model if live validation remains sound;
2. run the 15-question evaluation;
3. preserve failures;
4. update README;
5. generate example transcripts;
6. document latency as a known limitation if it remains;
7. commit everything;
8. push.

Do not add OCR implementation.
Do not add new features.
Do not benchmark more models.
Do not redesign the graph.
Do not chase perfect evaluation results.

We are now finishing the assignment, not expanding it.

Report the final:
- test count
- eval score
- median/typical latency
- failures
- known limitations
- model/provider
- commit hash

and stop.
