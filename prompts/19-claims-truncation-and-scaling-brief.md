The timeout investigation changes our understanding of the failure.

Do NOT treat increasing the timeout from 60s to 180s as the solution.

The important finding is:

- entity resolution succeeded
- graph traversal succeeded
- the correct 10 valves / 20 pipes were retrieved
- no tool loop occurred
- graph operations were deterministic across retries
- failure occurred during answer synthesis
- the generated claims block grew too large and was truncated at the 4096 output-token limit
- the adapter currently does not detect truncation
- the validator then interprets the incomplete claims block as invalid/missing

This is an architectural scaling issue in answer synthesis / grounding.

Continue the currently running Lightning benchmark first.

Do not change the default provider.
Do not start the official 15-question evaluation yet.

Once Lightning finishes, show the final candidate comparison and proposed model selection.

Then, before the official evaluation, implement a GENERAL fix for result-set scaling.

==================================================
1. DO NOT SOLVE THIS BY ONLY RAISING MAX TOKENS
==================================================

Do not simply:

- increase max_tokens
- increase timeout
- special-case the H1007 question
- special-case lists with 10 valves
- bypass grounding for long answers

A larger output limit may be useful as a safety margin, but it is not the architectural solution.

The protocol must scale to questions such as:

- list every pump and what it feeds
- list all valves downstream of X
- show all equipment connected through Y
- enumerate a larger result set

==================================================
2. INSPECT THE CURRENT CLAIMS PROTOCOL
==================================================

Before modifying it, report:

- exact format currently requested from the LLM
- why 10 valves result in ~30 claims
- what information is duplicated between:
  - human-readable answer
  - claims block
  - graph evidence
- how the grounding validator consumes claims
- whether every list item currently generates multiple individual claims
- current max output token configuration
- whether NVIDIA's response exposes a finish reason such as `length`
- whether the adapter currently preserves that finish reason

Quantify approximately where the token growth comes from.

==================================================
3. DETECT TRUNCATED MODEL OUTPUT
==================================================

Update the provider abstraction so response termination metadata is preserved where available.

If NVIDIA returns something equivalent to:

finish_reason = "length"

the system must recognize that the generation was truncated.

A truncated response must never be treated as a normal completed response.

Represent this explicitly, for example:

{
  "status": "truncated",
  "finish_reason": "length",
  ...
}

or through the project's existing typed response model.

Do not silently pass truncated output into normal parsing.

Add tests for this.

==================================================
4. REDESIGN CLAIM GROUNDING TO SCALE
==================================================

We already have structured deterministic graph evidence.

Do not force the LLM to restate every piece of graph evidence in a huge verbose claims block merely so we can validate information we already possess.

Design a more compact grounding representation.

Prefer evidence references.

Conceptually, graph tools should return stable evidence identifiers such as:

E1
E2
E3
...

For example:

E1 = H1007 resolved as PlateHeatExchanger-1
E2 = downstream traversal found valve V...
E3 = graph path/edge ...
...

The answer can then reference evidence compactly.

Example concept:

{
  "answer": "The downstream valves are ...",
  "evidence_refs": ["E2", "E3", ...]
}

OR, for list results:

{
  "answer": "...",
  "items": [
    {
      "text": "Valve X",
      "evidence_refs": ["E4"]
    },
    {
      "text": "Valve Y",
      "evidence_refs": ["E7"]
    }
  ]
}

The exact schema should fit the existing architecture.

Do not blindly implement my example if there is a cleaner representation.

The important properties are:

- evidence originates from graph tools
- evidence IDs are deterministic
- model references evidence rather than reproducing it
- validator verifies references exist
- graph-specific claims remain grounded
- output size grows approximately linearly and compactly
- large result sets do not require enormous duplicated claim blocks

==================================================
5. KEEP CLAIM-LEVEL GROUNDING
==================================================

Do not weaken grounding just to reduce tokens.

We still need to prevent:

- invented tags
- invented equipment
- invented pipes
- invented nominal diameters
- invented connections
- invented flow direction

Find the minimum structured representation required to validate these claims.

For simple enumeration, deterministic validation may be stronger than LLM-generated claims.

Example:

If the graph tool returns:

["V1", "V2", "V3"]

and the final answer enumerates those entities, validation should be able to verify the returned entity IDs/tags against graph evidence without requiring the LLM to write three verbose explanatory claims per entity.

==================================================
6. SEPARATE DATA FROM PRESENTATION
==================================================

The graph layer should produce structured facts.

The LLM should primarily turn those facts into natural language.

Conceptually:

Graph Tool
   |
   v
Structured Result
   |
   +--> Validator
   |
   v
LLM Presentation
   |
   v
Evidence References
   |
   v
Final Validation

Do not make the LLM reconstruct structured graph facts that the graph layer already knows.

==================================================
7. HANDLE LARGE RESULT SETS
==================================================

Test the revised design with different result sizes.

At minimum:

- 1 entity
- 3 entities
- 10 entities
- largest naturally occurring relevant result set available in C01

Measure:

- input tokens
- output tokens
- answer size
- number of claims/evidence refs
- validation success
- latency

We want to know that output size is controlled.

Do not fabricate synthetic plant facts merely to create a large list.

Use real graph results.

==================================================
8. RETEST THE H1007 QUESTION
==================================================

After the generic fix, run:

"Which valves are downstream of H1007?"

Run it at least 3 clean times with the selected candidate model.

Record:

- tool sequence
- number of valves retrieved
- number of pipes/path elements retrieved
- first-attempt grounded success
- rewrites
- truncation
- output tokens
- end-to-end latency
- unsupported claims

We should not require a rewrite merely because the answer contains 10 valid entities.

==================================================
9. INVESTIGATE THE SHALLOW P4712 RESULT
==================================================

Separately investigate this observation:

Question:
"List every pump and what it feeds."

P4712 currently reports a tee as its direct neighbour rather than the downstream equipment beyond that tee.

Do NOT immediately change the answer.

First determine what "feeds" means operationally in our graph model.

Inspect whether the graph contains intermediary topology nodes such as:

- tees
- nozzles
- piping segments
- connectors
- junctions

Determine whether a generic semantic traversal should pass through non-terminal topology nodes until it reaches meaningful process equipment.

We may need a general concept such as:

traverse_to_equipment(
    start,
    direction,
    pass_through_types=[...]
)

or an equivalent extension to the existing traversal tool.

But do NOT create a pump-specific implementation.

The same logic should work for:

"What does H1007 feed?"

"What equipment is downstream of X?"

"Where does X discharge?"

Before changing traversal semantics, inspect actual C01 topology and explain the proposed generic rule.

==================================================
10. TIMEOUT CONFIGURATION
==================================================

Keep provider timeout configuration separate from the truncation fix.

180 seconds may be reasonable for development/evaluation if NVIDIA occasionally has high latency.

But document that:

timeout != output truncation.

If the model returns a completed HTTP response with:

finish_reason=length

retrying with a longer HTTP timeout accomplishes nothing.

If appropriate, make timeout configurable:

LLM_TIMEOUT_SECONDS=...

Do not hide pathological latency with unlimited waits.

==================================================
11. TESTS TO ADD
==================================================

Add deterministic tests for:

- finish_reason=stop
- finish_reason=length
- truncated structured output
- truncated answer
- valid evidence references
- nonexistent evidence reference
- answer containing unsupported entity
- answer containing unsupported property
- compact grounding for list results
- 10+ result enumeration
- malformed evidence references

Existing hallucination tests must continue to pass.

==================================================
12. DO NOT CONTAMINATE THE OFFICIAL EVAL
==================================================

Do not modify implementation specifically around individual questions in the 15-question evaluation.

The changes must solve general classes of problems:

A. truncated structured output
B. duplicated evidence
C. large enumerations
D. topology intermediary traversal

After implementing the general fixes, freeze the architecture.

Only then run the official 15-question NVIDIA evaluation.

Preserve the current pre-fix candidate runs separately.

==================================================
13. REPORT BACK BEFORE OFFICIAL EVAL
==================================================

After Lightning finishes and after you have investigated the grounding protocol, report:

MODEL COMPARISON
- final results for all candidates
- proposed selected model

TRUNCATION
- current claims schema
- why it grows so large
- exact truncation detection available from NVIDIA
- proposed compact schema

TRAVERSAL
- why P4712 stops at a tee
- whether this reflects the raw graph or our traversal semantics
- proposed generic traversal rule

IMPLEMENTATION
- files that need changing
- tests to add
- whether any existing behavior changes

Do not start the official 15-question evaluation until these points are resolved.
