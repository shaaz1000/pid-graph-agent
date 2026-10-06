Do NOT run the full follow-up suite yet.

The second smoke shows the harness/evaluator fixes are working, but
gpt-oss-20b is not reliable enough on planner/tool choice or unknown coverage.

We will make TWO final generic workflow improvements, then compare a larger
Apache-2.0 model on the exact same smoke.

Do not make question-specific changes.

==================================================
1. APPROVE ONE RETRY AFTER FAILED FINAL SUBMISSION
==================================================

Today, if `submit_answer` is rejected during the forced-final step, the run ends
without giving the model a chance to repair the structured payload.

This caused avoidable R3 withholds.

Change this generically:

- if a structured `submit_answer` call fails schema/grounding validation on the
  forced-final step,
- return the deterministic validation error to the model,
- allow exactly ONE repair attempt,
- the repair attempt may ONLY use evidence already collected,
- no new graph/tool calls are allowed,
- then terminate regardless of outcome.

This is not an answer rewrite loop.
It is a structured-output repair.

Track separately:
- initial submission rejected
- repair attempted
- repair succeeded/failed

Add deterministic tests for:
- ambiguous `unknowns.about`
- invalid evidence id
- malformed field
- valid repair
- repair still invalid
- no extra graph calls during repair

Do not allow multiple retries.

==================================================
2. ADD GENERIC REQUEST-DECOMPOSITION / COVERAGE
==================================================

C1 exposed a generic failure:
the model answered the graph portion but did not account for a requested output
that was not supported by the drawing.

We already have the rule:
"For every requested conclusion that cannot be supported, add a typed unknown."

The 20B model often ignores it.

Do NOT add C1-specific wording.

Instead, before planning graph calls, require the model to produce a small
STRUCTURED request decomposition.

Example conceptually:

{
  "requested_outputs": [
    {
      "id": "q1",
      "description": "...",
      "kind": "entity_set | property | path | boundary | ordering |
               consequence | inventory | explanation | other"
    }
  ]
}

Do not use these exact enum values unless they fit the code cleanly.

The purpose is:

1. identify all independently requested parts of the question;
2. plan tools for each;
3. at `submit_answer`, require every requested output id to be accounted for by:
   - direct fact(s),
   - derived fact(s),
   - or an unknown.

This must be generic.

Examples of multi-part wording it should handle:

- "Which valves, in what order, and what cannot be isolated?"
- "Where is the measurement taken, what does it actuate, what is its fail
  position, and which line is it on?"
- "How many, where are they, and what properties do they have?"

Do not interpret domain truth at decomposition time.

This is request coverage, not answer reasoning.

==================================================
3. COVERAGE VALIDATION
==================================================

At final structured submission:

Every `requested_output_id` must appear in at least one:

- direct_fact.covers
- derived_fact.covers
- unknown.covers

If a requested output is omitted:
reject the structured submission with a deterministic error such as:

"Requested output q2 has not been addressed. Provide supported evidence or
mark it unknown."

This should naturally cause C1's closure-order request to become an unknown
without mentioning C1 or closure order in the prompt.

Add offline tests with unrelated synthetic questions.

==================================================
4. DO NOT ADD DOMAIN-SPECIFIC QUERY ROUTING
==================================================

Do NOT add mappings such as:

"isolate" -> isolation_boundary
"map loop" -> trace_instrumentation
"relief" -> all_paths

The planner must still choose generic tools.

Do not copy phrases from Sachin's examples into a dispatch table.

==================================================
5. KEEP ALL CURRENT STRUCTURED-GROUNDING DECISIONS
==================================================

Do not revert:

- application-rendered answers
- direct facts
- deterministic derived facts
- typed unknowns
- no trusted model commentary
- no semantic prose regex on the follow-up path
- evaluator contradiction fixes
- anchor-resolution classification
- unique name/tag resolution
- historical eval isolation

==================================================
6. MODEL COMPARISON: GPT-OSS-120B ONLY
==================================================

After all offline tests pass, determine the practical hosted option for:

openai/gpt-oss-120b

It must retain Apache-2.0/open-source compliance.

Check currently available configured providers first.

Preferred order:

1. existing Groq account if the model can actually complete the smoke within
   quota;
2. existing OpenRouter adapter if an API key is already configured and the
   model is available;
3. another already-supported hosted provider only if no architectural/provider
   work is needed.

Do not create a new provider integration.

Before making paid calls:

REPORT:
- provider
- exact model id
- whether existing credentials work
- current price if provider metadata/API exposes it
- estimated cost for the 11-run smoke
- estimated cost for the 150-run full suite

STOP before paid inference if the estimated full run is more than USD 15.

If the smoke itself is expected to cost under USD 5, proceed.

Do not expose any API keys.

==================================================
7. RUN EXACTLY THE SAME SECOND-SMOKE SET
==================================================

Use gpt-oss-120b only.

COMPLEX:
- C1
- C7
- C8

REPHRASING:
- R1a
- R1b
- R1c
- R1d
- R3a
- R3b
- R3c
- R3d

One run each.

Do NOT run 3 repeats yet.

No prompt/question changes relative to the official follow-up suite except the
new generic request-coverage mechanism.

==================================================
8. WHAT I WANT TO SEE
==================================================

For C1/C7/C8 report:

- correctness
- requested output coverage
- direct facts
- derived facts
- unknowns
- planner/tool choice
- repair attempt, if any
- latency
- model calls
- graph calls

For R1 and R3 report:

- factual result for each phrasing
- requested output coverage
- canonical fact set
- cross-phrasing consistency
- required-fact recall
- contradictions
- withheld
- tool choice differences
- entity resolution differences

==================================================
9. PASS CRITERIA FOR 120B
==================================================

Do not require perfection.

I would consider the larger model viable for the full run if:

COMPLEX:
- C1 explicitly accounts for closure-order request as unknown
- C8 remains complete
- C7 materially improves OR remains an honestly classified planning miss
- mean complex score >= 0.80

CONSISTENCY:
- no contradictions
- no more than 1 withheld across R1+R3
- at least one group fully cross-phrasing consistent
- other group >= 0.75 pair agreement
- substantial improvement over gpt-oss-20b required-fact recall

SAFETY:
- no unsupported process/safety prose reaches the user
- every requested output is accounted for structurally

==================================================
10. IF 120B STILL FAILS BADLY
==================================================

Do NOT tune the supplied questions individually.

Instead report that model planning variance remains the dominant limitation.

At that point we will decide between:

A. running the full suite honestly with the best compliant model,
or
B. making one architectural change to reduce planner freedom, such as a generic
   planning schema / capability selection layer.

Do not implement option B automatically.

==================================================
11. DO NOT COMMIT YET
==================================================

Keep this round uncommitted until the 120B smoke is reviewed.

Do not:
- run the full 150
- email Sachin
- change gold answers
- change supplied questions
- add phrase mappings
- tune individual failures
- touch C01/cross-P&ID historical artifacts

Return:
1. new test count
2. request-decomposition schema
3. final-repair behavior
4. provider/model/cost finding
5. full smoke table
6. R1/R3 consistency
7. comparison with 20B
8. recommendation: full run yes/no

STOP.
