We have a new follow-up from Sachin at Intuigence AI.

His feedback:

"I evaluated your current work. The questions seem quite simple, and I noticed extensive use of regex, which isn't a good practice for this type of task.

To evaluate the work, we would like to see:
1. Getting more complex questions answered about the P&IDs.
2. Same question rephrased in a different manner, ensuring the answer remains consistent across each turn.

You can use the attached PDF document to get some idea."

The attached document is:
PID_agent_followup_exercise.pdf

This is now the highest-priority task.

IMPORTANT:
Do not rush into implementation.
First inspect the current repository and the attached follow-up exercise in detail.

We need to satisfy the follow-up honestly and within roughly the requested 4-hour scope.

==================================================
FOLLOW-UP OBJECTIVE
==================================================

We now need to demonstrate two things:

1. COMPLEX MULTI-STEP P&ID REASONING
2. CONSISTENCY UNDER REPHRASING

The follow-up explicitly wants operational-style questions such as:

- isolation boundaries and closure order
- trip impact
- fail-position impact
- blocked-in equipment
- relief paths
- full control-loop mapping
- signal tracing
- inventories with attributes
- branch-aware line tracing
- upstream/downstream reach including recycle
- parallel paths
- process/control description

Every answer must remain grounded in the actual C01 P&ID.

Where the drawing is silent, say so.

Do not infer plant state, operating procedures, valve actuation behavior, relief adequacy, or process consequences unless supported by the graph/data.

==================================================
PHASE 1 — READ AND AUDIT BEFORE CHANGING CODE
==================================================

Read:

- the entire current repository
- the current README
- current graph tools
- entity resolver
- LangGraph workflow
- grounding/evidence validator
- evaluator
- saved C01 and cross-P&ID transcripts
- the attached PDF follow-up exercise

Then produce an audit answering:

1. Which of the complex question types can the current generic tools answer already?
2. Which require chaining existing tools?
3. Which require genuinely new GENERAL graph capabilities?
4. Which questions ask for semantics that are NOT represented in DEXPI and therefore must be answered with uncertainty/abstention?
5. Where is regex currently being used?
6. Which regex usage is merely deterministic parsing/validation and which regex usage is carrying semantic reasoning that should be replaced?
7. Which pieces of the current grounding validator are likely to be the reason Sachin said "extensive use of regex"?
8. What can be simplified or replaced by structured graph facts / typed relations rather than more regex?
9. Which follow-up questions would currently fail and why?
10. What is the smallest architecture change that improves generality rather than tuning for the provided examples?

DO NOT implement anything until this audit is complete.

==================================================
PHASE 2 — TREAT THE PROVIDED QUESTIONS AS EVALUATION, NOT RECIPES
==================================================

The PDF says the examples are not the spec.

Do NOT:
- add question-specific prompts
- add phrase-specific routing
- add "if question contains isolate..."
- add tool mappings for PIC / CCR / DN phrasing
- add expected-answer rules for C1–C15 or R1–R4
- add special cases for the given tags

The model should still choose from generic graph reasoning operations.

==================================================
PHASE 3 — ADDRESS THE REGEX FEEDBACK PROPERLY
==================================================

Sachin explicitly called out regex usage.

Do not respond by merely hiding regex or replacing one regex with another.

Audit all regex usage and separate it into categories:

A. harmless lexical parsing / identifier normalization
B. deterministic formatting / citation parsing
C. semantic fact validation
D. relation understanding
E. evaluation scoring

The concern is mainly C and D.

Where possible, move semantics into STRUCTURED REPRESENTATIONS.

Preferred direction:

- graph tools return typed facts
- relationships are represented as canonical predicates
- multi-hop paths are explicit structured chains
- answer generation cites structured evidence
- validator checks structured facts and chains
- prose is rendered from verified facts where possible

Avoid relying on natural-language relation regexes as the primary grounding mechanism.

Do not redesign the whole project if not necessary.

Timebox architectural changes.

==================================================
PHASE 4 — COMPLEX REASONING CAPABILITIES
==================================================

Inspect whether the current 7 tools are enough for the requested complex questions.

Prefer COMPOSITION of generic operations rather than many new domain-specific tools.

Possible generic capabilities to consider, only if needed:

- enumerate_boundary_edges(entity/subgraph)
- find_all_paths(source, target, constraints)
- trace_signal_chain(start)
- find_cut_set / isolating boundary
- reachable_after_removing(edges/nodes)
- branch-aware line traversal
- graph neighborhood with typed relationships
- collect_attributes(entity_set, properties)
- identify open-ended connections
- relief-path reachability

But do NOT create tools named after evaluation questions.

For example, do NOT create:

isolate_T4750()
answer_trip_question()
blocked_in_checker_for_C01()

If adding a tool, define the general graph operation it represents.

==================================================
PHASE 5 — SAFETY / SEMANTIC BOUNDARIES
==================================================

Be extremely careful with questions like:

"If P4712 trips, what loses flow?"
"If valves fail closed, does pressure rise?"
"Can equipment become blocked in without relief?"
"What order would you close valves?"

A P&ID often gives topology and fail position, but not enough to prove transient process behavior or safe operating procedure.

For each such question distinguish:

- directly represented graph fact
- graph-derived topology consequence
- process-engineering inference
- information absent from drawing

The answer should clearly label the last two.

Do not claim real-world safety conclusions from topology alone.

For "order you would close them":
if closure order is not represented, say the drawing identifies the isolation boundary but does not specify a safe operating sequence.

This is important.

==================================================
PHASE 6 — PROVIDED COMPLEX QUESTIONS
==================================================

The PDF includes 15 complex examples C1–C15.

Create a structured eval suite for ALL of them.

But before any LLM run:

For each question:
- derive what can be answered deterministically from the graph
- list required graph facts
- list facts that are NOT present
- define acceptable abstention/qualification
- define expected answer components
- define forbidden unsupported claims

Do not let the LLM create its own gold answer.

If a question cannot be fully answered from C01, that is an expected partial/qualified answer, not a failure.

==================================================
PHASE 7 — REPHRASING CONSISTENCY
==================================================

The provided PDF includes groups R1–R4.

Each group expresses the same underlying intent with different wording.

We need a consistency evaluator that compares FACTS, not raw strings.

Do NOT compare answers by text similarity.

Normalize each answer into a structured fact set such as:

{
  entities: [...],
  relations: [...],
  properties: [...],
  paths: [...],
  abstentions: [...]
}

or reuse the existing verified evidence/fact representation.

Two answers are consistent if the verified factual content agrees.

Differences in prose/order are fine.

Important consistency dimensions:

- same entity resolution
- same topology result
- same property values
- same paths/boundaries
- same abstentions
- no contradictory facts

==================================================
PHASE 8 — THREE REPEATS PER PHRASING
==================================================

The PDF requires:

"Ask every phrasing in each group as a separate turn, 3 times each."

Automate this.

For each phrasing:
- run independently
- no conversation history
- same model/config
- 3 repeats

Measure:

A. within-phrasing repeat consistency
B. cross-phrasing consistency
C. overall group consistency

Do not just report one percentage.

Classify inconsistency causes:

- entity resolution
- planner/tool choice
- graph retrieval
- incomplete traversal
- answer synthesis
- grounding rejection
- provider/model variance
- ambiguity in the question
- missing graph data

==================================================
PHASE 9 — OPTIONAL CONVERSATIONAL CONSISTENCY
==================================================

The PDF says conversation-history testing is optional.

Do NOT prioritize this unless the mandatory work is complete.

The current agent is primarily single-turn.

If there is no conversation memory today, document that and leave it optional.

==================================================
PHASE 10 — ADD OUR OWN COMPLEX QUESTIONS
==================================================

The follow-up requires:

- at least 10 MORE complex questions
- at least 5 MORE rephrasing groups
- each group 4+ phrasings
- at least 2 groups based on complex questions

Do not generate these blindly.

First inspect C01 and derive genuinely challenging questions from the graph.

Our additional complex questions should cover categories NOT duplicated too heavily from C1–C15.

Good candidates may include:

- multi-branch route comparison
- nearest isolation boundary
- path alternatives after removing one valve
- instrument-to-final-element tracing
- equipment inventory constrained by line/property
- reachability through recycle
- open-end detection
- path with intermediate valve/fitting enumeration
- compare two routes
- ambiguous entity phrasing
- property-based entity identification
- topology change under hypothetical removal

But only include questions whose expected facts can be independently derived from graph operations.

==================================================
PHASE 11 — EVALUATION DESIGN
==================================================

We need a proper follow-up evaluator.

Separate metrics:

COMPLEX QUESTION SCORE
- correct
- partial
- abstained appropriately
- incorrect
- unsupported claims

REPHRASING CONSISTENCY
- repeat consistency per phrasing
- cross-phrasing consistency per group
- factual contradiction count
- entity-resolution consistency
- path/property consistency

GROUNDING
- unsupported final claims
- withheld answers
- limited answers

EFFICIENCY
- LLM calls
- tool calls
- median latency
- mean latency

Do not collapse all of this into one misleading score.

==================================================
PHASE 12 — DO NOT RUN EVERYTHING YET
==================================================

NVIDIA inference is expensive and variable.

First:

1. audit
2. implement minimal generic improvements
3. build deterministic gold
4. run offline tests
5. run ONLY a small smoke subset

Smoke subset should include:

- 3 complex questions from the PDF
  - one isolation/topology
  - one control-loop/signal
  - one relief/blocked-in or fail-position question

- 2 rephrasing groups
  - 4 phrasings each
  - ONE run each initially, not 3 repeats yet

Then STOP.

Report before running the full mandatory suite.

==================================================
PHASE 13 — WHAT I WANT IN YOUR FIRST RESPONSE
==================================================

Do NOT code yet.

Return:

1. Exact interpretation of Sachin's feedback.
2. Summary of the follow-up PDF requirements.
3. Audit of regex usage:
   - file
   - purpose
   - category A/B/C/D/E
   - whether it should remain or be replaced
4. Which C1–C15 questions current architecture can answer now.
5. Which would fail or require qualification.
6. Which generic capabilities are missing.
7. Minimal architecture changes proposed.
8. Proposed structured consistency metric.
9. Proposed 10+ additional complex questions.
10. Proposed 5+ new rephrasing groups with 4+ phrasings each.
11. Proposed smoke-test subset.
12. Estimated NVIDIA calls and runtime for:
   - smoke
   - full complex suite
   - full 3x consistency suite
13. Risks:
   - overfitting
   - safety inference
   - regex semantics
   - model variance
14. What you recommend doing within the requested 4-hour timebox.

STOP after this analysis.

Do not:
- modify code
- run NVIDIA
- commit
- push
- email Sachin
until I approve the plan.
