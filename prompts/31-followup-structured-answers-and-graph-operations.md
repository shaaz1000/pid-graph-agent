Approved, with several refinements.

Your interpretation of Sachin's feedback is correct.

We will proceed with the follow-up exercise, but I want the architecture to answer the criticism directly rather than adding another layer of regex.

The priorities are:

1. genuinely complex multi-step graph reasoning;
2. consistency under rephrasing;
3. structured grounding instead of semantic regex over prose;
4. strict separation between facts, deterministic graph-derived consequences, and information the P&ID does not contain;
5. no question-specific logic.

Do NOT run the full NVIDIA/model evaluation yet.

==================================================
DECISION 1 — STRUCTURED ANSWER PATH APPROVED
==================================================

Approved, but modify your proposal.

Do NOT make free-text `inferences` a first-class grounded fact type merely because the identifiers in the sentence exist in cited rows.

That would still allow unsupported semantic conclusions.

The primary answer contract should instead distinguish:

A. DIRECT FACTS
Facts explicitly represented in graph/tool results.

Examples:
- valve X has fail action Close
- line Y has nominal diameter DN 80
- instrument A sends a signal to function B
- P4711 is connected to H1007 through line 47122

B. DERIVED FACTS
Facts computed deterministically by graph algorithms from the graph.

Examples:
- after removing valve V, T4750 is no longer reachable from P4711
- valves V1 and V2 form the graph isolation boundary around equipment E
- two distinct graph paths exist between A and B
- no path from equipment E to a represented relief device exists in this drawing

These must be produced by code/tool operations, not by the LLM reasoning in prose.

Each derived fact must retain provenance:
- source graph entities/edges
- operation used
- relevant removed/blocked nodes where applicable

C. NOT IN DRAWING / UNKNOWN
For claims the P&ID does not establish.

Examples:
- safe valve closure order
- actual process pressure response
- real-time operating state
- whether relief sizing is adequate
- where an off-page line ultimately terminates
- actuator type if absent

D. OPTIONAL ENGINEERING COMMENTARY
Only if genuinely useful.

It must be visibly labelled:
"Engineering interpretation, not stated in the P&ID"

It must NOT:
- count as a grounded graph fact;
- count toward factual consistency scoring;
- silently become an expected answer.

For the scored follow-up path, prefer A+B+C and avoid D wherever possible.

==================================================
STRUCTURED SUBMISSION CONTRACT
==================================================

Implement a schema-validated final answer action/function such as:

submit_answer({
  direct_facts: [...],
  derived_facts: [...],
  unknowns: [...],
  summary: ...
})

Design the exact schema yourself after inspecting existing typed models.

Each direct fact should point to evidence/fact ids.

Each derived fact should point to the deterministic graph operation/result that produced it.

Unknowns should be typed/category-based where practical, not parsed from prose.

The application should render the final human-readable answer from this structured object.

The LLM should not be responsible for retyping plant facts if code can render them.

==================================================
REGEX DIRECTION
==================================================

Sachin explicitly criticised regex use.

The new structured path should make these no longer necessary as the PRIMARY grounding mechanism:

- relation-word regex
- hedge/disclaimer regex
- negation semantics regex
- prose fact extraction regex
- plant-statement regex

Do not delete legacy code recklessly if existing historical tests/artifacts depend on it.

Instead:

1. make structured answers the primary follow-up path;
2. retire the semantic regex validator from that path;
3. leave legacy parsing only for:
   - historical evaluation compatibility;
   - citation formatting;
   - lexical identifier handling;
   - optional lint/fallback.

README/design note must explain this clearly.

Do NOT replace the current regex list with a larger NLP regex list.

==================================================
DECISION 2 — GENERIC COMPLEX GRAPH OPERATIONS
==================================================

Proceed with the generic capabilities you identified.

I approve these concepts:

1. isolation / cut boundary
2. reachability and all-path reasoning with blocked/removed nodes
3. instrumentation-chain tracing
4. list/filter entities with requested attributes

Also investigate C12 specifically.

If line 47126 branch tracing cannot be cleanly expressed through an existing generic operation, add ONE generic line/network operation such as:

trace_line(line_identifier, include_branches=true)

or an equivalent generic graph-service capability.

It must work for arbitrary lines/datasets.

Do not make a C12-specific helper.

==================================================
IMPORTANT SEMANTIC RULE
==================================================

Use graph algorithms for hypothetical topology whenever possible.

For example:

"If valve X closes, can A still reach B?"

should become:

graph reachability with X removed/blocked

NOT:

LLM guesses what happens to plant flow.

Likewise:

"Can equipment become blocked in?"

may support a statement such as:

"With these represented boundary valves treated as closed, the equipment region has no represented graph path to a relief device."

Do NOT convert that into:

"The equipment is unsafe"
or
"pressure will rise"

unless the drawing explicitly contains enough information, which it normally will not.

==================================================
ISOLATION ORDER
==================================================

The PDF asks for valve closure order.

The P&ID does not encode an operating procedure.

Therefore:

- identify the isolation boundary deterministically;
- report any connections that cannot be isolated from this drawing;
- explicitly state that safe closure order is not specified by the P&ID.

Do not invent an order merely to satisfy the example.

This should be reflected in deterministic gold expectations.

==================================================
TRIP / FAIL-POSITION QUESTIONS
==================================================

Distinguish:

KNOWN:
- actuator fail action if encoded;
- topology before/after removing a path;
- represented signal relationships.

DERIVED:
- graph reachability after a valve is treated as closed/open according to encoded fail position.

UNKNOWN:
- actual hydraulic flow;
- pressure increase/decrease;
- transient dynamics;
- whether a reading physically rises/falls unless explicitly represented.

For C5-type questions, topology may support what becomes isolated but not necessarily whether PI4712.01 rises or falls.

The correct response may explicitly say that the direction of the pressure change cannot be determined from the P&ID alone.

==================================================
CONSISTENCY EVALUATOR APPROVED
==================================================

Your fact-set approach is correct.

Do NOT use answer string similarity as the main metric.

Canonicalize structured output into:

- resolved entities
- direct relations
- properties
- deterministic derived relations
- ordered paths where ordering matters
- unordered boundaries/sets where ordering does not matter
- unknown/not-in-drawing categories

Then calculate separately:

1. WITHIN-PHRASING REPEAT CONSISTENCY
Three repeats of one wording.

2. CROSS-PHRASING CONSISTENCY
Different wording within the same intent group.

3. CONTRADICTION RATE
Same subject/property/relation yielding incompatible values.

4. ENTITY-RESOLUTION CONSISTENCY

5. REQUIRED-FACT RECALL
Compared with deterministic gold.

6. UNSUPPORTED-FACT COUNT
Ideally structural now, rather than regex-derived.

Also report Jaccard overlap only as a secondary descriptive metric.

==================================================
DO NOT TREAT EXTRA CORRECT FACTS AS INCONSISTENCY
==================================================

Consistency should be based primarily on GOLD-RELEVANT facts.

Example:

Answer A:
P4711 -> H1007 -> T4750

Answer B:
P4711 -> H1007 -> T4750
and also mentions line 47122

Those answers can still be consistent regarding the requested intent.

However contradictions must always count.

==================================================
RESOLUTION UNDER REPHRASING
==================================================

Do not hardcode aliases from the provided R groups.

For phrases such as:

"84 kW pump"
"recip pump"
"plate exchanger"
"hand-switched valve"

prefer general resolution using:

- type tokens
- properties
- descriptions
- candidate filtering
- LLM interpretation over candidate metadata if necessary

For abbreviations, do NOT create a table containing phrases from the PDF.

A generic unique-prefix/type-token mechanism is acceptable if it is genuinely general.

Example:
"recip" matching "reciprocating" only when unambiguous.

Test it using words/tags NOT present in the supplied follow-up examples as well.

==================================================
OPEN-SOURCE MODEL COMPLIANCE — IMPORTANT
==================================================

Before the final follow-up evaluation, audit this requirement carefully.

Sachin's PDF explicitly says:

"Keep using an open-source LLM for the agent."

Our current Nemotron 3 Super submission model is open-weight under the NVIDIA Nemotron Open Model License, not OSI-approved open source.

Do NOT ignore this.

We already have provider abstraction and an Apache-2.0 option:
openai/gpt-oss-20b via Groq.

Do NOT immediately switch the whole implementation.

First report:

1. exact model candidates already supported that clearly satisfy an OSI/open-source licence;
2. whether our existing Groq gpt-oss-20b endpoint/key is currently usable;
3. whether quota is sufficient for this follow-up;
4. smallest representative smoke comparison:
   - one complex isolation question
   - one multi-hop loop question
   - one rephrasing group or two representative phrasings
5. latency and tool-calling reliability.

Timebox model compliance investigation to 20 minutes.

If no usable compliant hosted model is available, STOP and tell me.
Do not silently submit the follow-up using an open-weight-only model while claiming compliance.

Do not benchmark a dozen models.

==================================================
RECORD KEEPING APPROVED
==================================================

Yes.

Save:

- the follow-up PDF unchanged in an appropriate docs/reference location IF licence/privacy considerations allow;
- otherwise document its filename and requirements without committing the attachment itself.

Save this instruction as the next prompt/spec under prompts/, preserving real history.

Do not rewrite earlier prompts.

==================================================
ADDITIONAL COMPLEX QUESTIONS
==================================================

Your proposed 12 are approved as candidates.

Before putting them into the scored suite:

- deterministically derive their gold;
- remove any question whose requested conclusion is not objectively scoreable from C01;
- ensure we are not simply duplicating C1-C15.

Target 10-12 final additional complex questions.

==================================================
ADDITIONAL REPHRASING GROUPS
==================================================

Your proposed G1-G6 are directionally good.

Before finalizing:

- ensure at least 5 groups;
- 4+ phrasings each;
- at least 2 based on complex multi-step questions;
- test resolution diversity:
  tag
  type
  property
  abbreviation/shorthand
  route/context description

Do not copy phrasings into system prompts or resolver aliases.

==================================================
EVALUATION PROVENANCE
==================================================

This is a NEW follow-up evaluation.

Do not alter:

- original C01 baseline
- cross-P&ID baseline
- their transcripts
- their scores

Create a separate namespace such as:

evals/followup/
  complex/
  consistency/
  runs/
  smoke/

Record:

- commit SHA
- dirty state/diff hash
- model/provider
- temperature
- run id
- question/group id
- repeat index
- tool trace
- structured answer
- facts
- latency
- tokens
- score
- consistency result

==================================================
FIRST IMPLEMENTATION STAGE
==================================================

Proceed with:

1. structured answer path;
2. generic complex graph operations;
3. deterministic gold for C1-C15;
4. deterministic gold for 10-12 own complex questions;
5. consistency evaluator;
6. R1-R4 plus at least 5 own groups;
7. offline tests.

DO NOT run the full follow-up evaluation.

After offline work passes, run only this smoke:

COMPLEX:
- C1 isolation
- C8 control-loop mapping
- C7 relief path

REPHRASING:
- R1a-d, one run each
- R3a-d, one run each

If open-source model compliance requires changing the provider, use the compliant model selected by the small model-compliance check.

For the smoke report include:

- question
- structured direct facts
- deterministic derived facts
- unknowns
- final rendered answer
- tools used
- correctness
- grounding
- latency
- model calls
- tool calls

For R1 and R3 also show:

- canonical fact set per phrasing
- consistency result
- any contradiction
- entity-resolution differences

==================================================
STOP AFTER SMOKE
==================================================

Return:

1. files changed
2. tests passing
3. regex removed/bypassed from the primary follow-up path
4. new generic graph capabilities
5. exact structured answer schema
6. open-source-model compliance finding
7. smoke results
8. R1/R3 consistency
9. failures/limitations
10. estimated cost/runtime for full mandatory follow-up
11. whether you recommend proceeding

Do not:
- run the full suite
- run 3 repeats yet
- email Sachin
- optimize against smoke failures
- add question-specific logic
- add more features
- touch historical eval artifacts

STOP and wait for approval.
