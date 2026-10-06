Approved with the following decisions.

Do NOT run the full follow-up suite yet.

We are fixing only generic harness / evaluator issues exposed by the smoke.

==================================================
1. REMOVE FREE-TEXT MODEL PROSE FROM THE SCORED PATH
==================================================

For the follow-up structured-answer path:

Do not render model-authored `summary` or `commentary` to the user.

The final answer should be application-rendered only from:

- verified direct_facts
- verified derived_facts
- typed unknowns

The model may internally provide a short summary field if useful for debugging,
but it must not be shown as trusted answer content and must not affect scoring.

Reason:
the smoke demonstrated that a free-text summary can reintroduce unsupported
process/safety claims even when the structured facts are valid.

Example found:
an invented closure sequence plus "safe depressurization".

Do not solve this with another prose validator.

The scored user-visible path should contain no unverified free-form factual prose.

==================================================
2. UNKNOWN COVERAGE MUST BE GENERIC
==================================================

The structured answer contract must require the model to account for every
material part of the user's request.

Add a generic instruction:

"For every requested conclusion or output component that cannot be supported by
a direct fact or deterministic derived fact, add a typed unknown explaining what
the drawing does not establish."

This applies generally, not to specific questions.

Examples:
- requested closure order but no procedure is encoded
- requested pressure tendency but hydraulics are not represented
- requested off-page destination but it is outside the drawing
- requested actuator type but it is absent

Do not add C1/C5-specific instructions.

Add offline tests using synthetic/general examples.

==================================================
3. FIX THE TWO EVALUATOR DEFECTS
==================================================

Approved.

These are measurement bugs, not model tuning.

A. FALSE CONTRADICTIONS

Do not attribute a sub-object property to its owner if doing so collapses
distinct sub-objects into one property slot.

Example:
two nozzle tags on one pump must not be treated as contradictory values of a
single pump property.

Canonical facts should retain the actual subject that owns the property.

Add tests for:
- multiple nozzles on one item
- multiple chambers
- repeated legitimate multi-valued attributes
- true contradictions still detected

B. WRONG ENTITY-RESOLUTION FAILURE LABELS

Separate:

- question/input anchor resolution
from
- answer/result entity discovery

A model that resolves the starting entity correctly but fails to reach the
target later must be classified as planning/traversal, not entity resolution.

Add regression tests.

==================================================
4. APPROVE TWO GENERIC HARNESS ROBUSTNESS FIXES
==================================================

These are approved because they are provider/schema robustness fixes, not
question-specific changes.

A. MALFORMED STRUCTURED TOOL NAME NORMALIZATION

Observed form:
`submit_answer<|channel|>commentary`

Handle provider-added channel/control suffixes generically in the model adapter
before tool dispatch.

Requirements:
- only normalize known protocol/control-token contamination
- do NOT fuzzy-match arbitrary tool names
- invalid unknown tool names must still fail
- add tests for clean name, contaminated known name, unknown name

B. `unknowns.about`

Allow the structured answer interface to accept either:

- canonical entity ids
or
- entity names/tags that resolve uniquely to canonical ids

Resolution must use the existing generic resolver.

If ambiguous:
reject or ask the model to clarify structurally.

Do not silently choose among multiple matches.

Add tests:
- canonical id
- exact tag
- unique normalized name
- ambiguous name
- unknown name

==================================================
5. DO NOT ADD MORE QUESTION-SPECIFIC PROMPTING
==================================================

Do not encode:
- C1 closure order
- C7 relief behavior
- C8 loop structure
- R1/R3 phrasing
- any provided expected answer

The system prompt may describe only generic reasoning rules and the structured
answer contract.

==================================================
6. REVIEW C7 BEFORE FULL RUN
==================================================

The smoke showed both models found only one route and did not ask for all routes.

Inspect whether the generic graph API makes "all routes to a relief device"
sufficiently discoverable.

Do NOT add a C7-specific tool.

If current `find_path(all_paths=true)` already supports it, improve only the
generic tool description so the model understands:

- use single shortest path when the question asks for "a path"
- use all_paths when the question asks whether ANY/ALL alternative routes exist
  or asks about route availability under conditions

Keep wording generic.

If a new tool is unnecessary, do not add one.

==================================================
7. R3 GOLD STRICTNESS
==================================================

Review R3a carefully.

If:
"Map all connections for PICSA4712.02"

can reasonably mean only direct connections, do not force a full-loop answer in
the per-question correctness gold unless the supplied follow-up document clearly
defines the entire R3 group as equivalent to C8.

For consistency-group scoring:
the group can still compare the common intended semantic target.

But distinguish:

- individual question correctness
from
- group semantic consistency target

Do not penalize a literally valid direct-connections answer as factually wrong
just because another paraphrase asks for the full loop.

Document this decision.

==================================================
8. MODEL DECISION
==================================================

Use an OSI-compatible/open-source model for the official follow-up.

Current default decision:

`openai/gpt-oss-20b` via NVIDIA

Reason:
- Apache-2.0
- usable with existing key
- feasible runtime
- satisfies the follow-up requirement more cleanly than Nemotron

Keep Nemotron smoke results only as diagnostic/reference artifacts.

Do NOT use Nemotron for the official scored follow-up unless Sachin explicitly
approves open-weight licensing.

Do NOT use Groq gpt-oss-120b for the full run unless the quota/runtime situation
changes.

==================================================
9. OFFLINE REGRESSION FIRST
==================================================

After implementing the above:

Run the full offline deterministic tests.

Then rerun ONLY the same smoke set:

Complex:
- C1
- C7
- C8

Consistency:
- R1a-d one run each
- R3a-d one run each

Use only:
`openai/gpt-oss-20b` via NVIDIA

No Nemotron comparison this time.

We want to verify the official path, not benchmark models.

==================================================
10. SMOKE PASS CRITERIA
==================================================

Do not require 100% correctness.

But before full run, require:

- no unsupported free-text safety/procedure claims can reach the final answer
- no malformed known tool name causes a withhold
- unknown names/tags in structured fields resolve generically
- evaluator reports no false contradictions
- evaluator correctly classifies resolution vs planning failures
- C1 includes closure order as unknown if not represented
- C8 remains fully mapped
- no question-specific logic is introduced

For C7, report whether failure is:
- model planning
- tool discoverability
- graph representation
- missing drawing data

Do not tune specifically to C7 after that classification.

==================================================
11. AFTER THE SECOND SMOKE
==================================================

Return:

1. files changed
2. test count
3. exact user-visible structured answer format
4. confirmation free-form model prose is not shown
5. evaluator fixes
6. provider/tool-name robustness result
7. unknown resolution result
8. C1/C7/C8 scores
9. R1/R3 consistency
10. failure classifications
11. estimated full-run time/tokens
12. recommendation whether to proceed with full mandatory run

Do not:
- run the 150-run full suite
- commit/push yet unless the smoke is healthy
- email Sachin
- alter historical eval artifacts
- add question-specific rules

STOP and wait for approval.
