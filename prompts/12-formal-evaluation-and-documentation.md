We are changing execution strategy because of the assignment's explicit
4–6 hour timebox.

Do NOT wait for Groq before moving forward.

The implementation remains frozen at:

a8d56b312e831d7ace33a267f251a9171e62f1d1

Current state:

- 398 deterministic tests passing
- 4 live tests deselected
- DeepSeek diagnostic completed:
  6 correct
  1 partially correct
  1 correct draft withheld by grounding
- the two general issues discovered by that diagnostic were subsequently fixed
- Groq GPT-OSS verification is currently blocked by provider quota

We are now moving to M3 using DeepSeek so that the assignment can be completed
within the intended engineering timebox.

IMPORTANT:

This does NOT authorize additional agent tuning.

The architecture is frozen.

============================================================
0. SAVE THIS PROMPT
============================================================

Save this complete instruction as the next sequential prompt under prompts/.

Update the prompt index.

Do not modify historical prompts.

============================================================
1. FREEZE CHECK
============================================================

Before M3 record:

git rev-parse HEAD
git status --short

HEAD must be:

a8d56b312e831d7ace33a267f251a9171e62f1d1

The implementation working tree must be clean.

Do not modify production code during M3.

============================================================
2. M3 PURPOSE
============================================================

Build the small formal evaluation required by the assignment:

10–20 questions
expected answers
scoring script
actual score

Use 15 questions.

The evaluation must measure generalization over the real C01 pyDEXPI graph.

It must NOT merely repeat the development questions.

Do not optimize the agent against this evaluation after seeing results.

This is measurement.

============================================================
3. EVALUATION CATEGORIES
============================================================

Construct a balanced 15-question evaluation covering approximately:

ENTITY RESOLUTION / AMBIGUITY
- exact entity resolution
- type/description resolution
- ambiguous identifier

ADJACENCY
- immediate connections
- associated pipes/lines

REACHABILITY
- upstream/downstream traversal
- multiple branches
- terminal versus truncated frontier

PATHS
- route between two entities
- properties of elements along a route

PROPERTIES
- equipment property
- line/segment property
- chamber-specific property
- missing property

INSTRUMENTATION
- instrumentation relationship
- controller/actuator/sensing relationship where represented in the graph

ROBUSTNESS
- nonexistent identifier
- unsupported assumption / missing graph fact

Do not force exactly one question per bullet.

The total must be 15 and reasonably balanced.

============================================================
4. AVOID DEVELOPMENT-SET LEAKAGE
============================================================

Do not simply reuse the eight DeepSeek diagnostic questions.

Do not simply reuse the five frozen Groq verification questions.

Some underlying graph concepts/entities may naturally overlap because the C01
graph is small, but wording and information requests should test broader
generalization.

Prefer different entities, relationships and formulations where the graph
supports them.

Do not manufacture facts merely to obtain variety.

============================================================
5. EXPECTED ANSWERS MUST COME FROM THE GRAPH
============================================================

Before running the LLM evaluation, derive the expected facts using the
deterministic graph layer.

Do NOT ask the LLM to create the gold answers.

For every evaluation item store enough structured expected information to
score the answer objectively.

For example, where appropriate:

expected entity ids
expected tags
expected relationship
expected direction
expected line/segment
expected property/value/unit
expected ambiguity
expected missing-data behavior
expected path facts

The exact schema may vary by question type.

Gold answers must be based on deterministic graph evidence.

============================================================
6. DO NOT HAND-WRITE FAKE EXPECTATIONS
============================================================

Use the real C01 graph.

If an intended evaluation question cannot be given a defensible expected
answer from the deterministic graph:

replace that evaluation question before the live run.

Do not guess.

Do not infer process facts absent from the graph.

============================================================
7. SCORING
============================================================

Implement a small deterministic scoring script.

Do NOT use another LLM as the primary judge.

Score graph-backed factual requirements.

A reasonable design is per-question required facts with partial credit.

For example:

required factual assertions satisfied / required factual assertions

plus explicit handling for:

ambiguity
not-found
missing-data expectations
unsupported claims

Do not require exact prose matching.

Do not penalize harmless wording differences.

Do penalize:

- missing required graph facts
- wrong graph facts
- unsupported plant claims
- incorrect direction
- presenting a truncated frontier as terminal
- inventing missing properties
- guessing through ambiguity

Keep scoring understandable enough to explain in the README.

============================================================
8. SEPARATE TOOL/WORKFLOW QUALITY FROM ANSWER SCORE
============================================================

Where practical, record diagnostic metrics separately from the factual score:

- model calls
- tool calls
- grounding result
- regeneration
- fallback
- turn-limit hit
- unsupported claims

Do not bake every efficiency metric into the correctness score.

The main eval score should measure factual task performance.

============================================================
9. PROVIDER FOR THIS RUN
============================================================

Use:

LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

Use runtime overrides.

Do not edit .env.

Do not run Groq.

Do not use OpenRouter.

Do not implement failover.

Record explicitly that this evaluation run used:

provider: deepseek
model: deepseek-chat

Do not describe this run as GPT-OSS.

============================================================
10. RUN EACH QUESTION ONCE
============================================================

Once the 15 questions and expected answers are frozen:

save them.

Record the Git state.

Then run each question exactly ONCE.

No retries for semantic failures.

No implementation changes between questions.

No prompt changes.

No graph changes.

No expected-answer changes after observing model output.

No cherry-picking.

If infrastructure prevents a question from completing, record:

infrastructure_failure

Do not silently rerun it.

============================================================
11. CAPTURE TRANSCRIPTS
============================================================

For every evaluation question capture:

- exact question
- expected graph facts
- final answer
- complete visible workflow/tool trace
- tool results or compact representations necessary to understand the trace
- model calls
- tool calls
- token usage
- latency
- grounding result
- regeneration
- fallback
- unsupported claims
- factual score
- outcome

Outcome:

correct
partially_correct
incorrect
abstained
infrastructure_failure

============================================================
12. NO TUNING AFTER RESULTS
============================================================

After the 15-question run:

DO NOT modify the agent.

DO NOT modify the evaluation gold answers to make results look better.

DO NOT rerun failed questions.

DO NOT remove difficult questions.

DO NOT replace failed questions.

The first frozen run is the reported run.

============================================================
13. EVALUATION OUTPUT
============================================================

Produce an eval artifact in the repository containing:

- the 15 questions
- expected graph-backed answers/facts
- actual answers
- scores
- aggregate score

Also preserve enough raw run information to reproduce or inspect the results.

Use the existing repository organization if there is already an appropriate
place.

Do not over-engineer storage.

============================================================
14. EVALUATION SCRIPT
============================================================

The assignment requires:

"a script that scores them"

Ensure there is a clear one-command scoring path.

For example, conceptually:

uv run python scripts/eval.py

or an equivalent existing CLI command.

Do not add a large evaluation framework.

The scoring implementation should be small and readable.

============================================================
15. TRANSCRIPTS FOR README
============================================================

From the actual runs select 5–10 representative transcripts.

Target 7 if enough useful examples exist.

They should demonstrate different behavior classes.

Include at least TWO where the agent fails or struggles, as Abdullah explicitly
requested.

"Struggles" may include:

- ambiguity
- missing data
- grounding regeneration
- partial answer
- traversal limitation
- documented graph limitation

Do not fabricate failures.

Use actual runs.

Do not hide poor behavior.

============================================================
16. README REQUIREMENTS
============================================================

After M3 results exist, update the README to satisfy the assignment.

It must include:

1. HOW TO RUN

Clone:
one command or normal clone command

Install:
at most one command

Run a question:
at most one command

Clearly document required environment configuration.

2. DESIGN NOTE

Keep it under approximately one page.

Explain:

- pyDEXPI ProteusSerializer
- GraphLoader
- GraphAbstractor
- conceptual graph versus plant graph
- why the dual-graph abstraction exists
- deterministic entity resolution
- graph traversal tools
- LLM planning
- grounding
- visible workflow

Use this core statement:

"The LLM interprets intent and plans graph operations; it is not the source
of plant knowledge. All factual answers are derived from deterministic
operations over the pyDEXPI graph."

3. GRAPH ABSTRACTION

Explain briefly:

conceptual graph:
equipment-level topology and process-direction traversal

plant graph:
engineering properties, hierarchy and provenance

recovered open ends:
explicitly marked and graph-derived, never fabricated destinations

chamber-aware traversal:
prevents crossing exchanger sides incorrectly

4. AGENT DESIGN

Explain generic tools:

find_entities
list_entities
get_entity
get_connections
traverse
find_path
get_properties

Explain:

plan
execute tools
continue planning if necessary
draft answer
ground
optional regeneration
finalize

5. EXAMPLE TRANSCRIPTS

5–10 actual examples.

At least two failures/struggles.

Show visible tool workflow.

6. EVALUATION

Document:

15 questions
how gold facts were generated
how scoring works
provider
model
actual score
limitations

Do not invent the score.

7. LIMITATIONS

Include honest known limitations such as applicable:

- source graph abstraction can lose details
- chamber handling required plant-graph recovery
- some components lack human-readable tags
- slash-joined identifier grounding may trigger regeneration
- instrumentation-code glosses from model knowledge are not always detectable
- model may perform redundant calls
- no perfect deterministic evidence-sufficiency detector
- provider/model behavior varies
- topology represents the graph, not live valve state/process operation

Only include limitations that remain true.

8. TIME SPENT

Report the actual approximate engineering time.

Do not invent a lower number to match the requested timebox.

If exact time is not tracked, provide an honest approximation.

============================================================
17. PROVIDER DOCUMENTATION
============================================================

The implementation is provider-configurable.

Document the supported provider configuration accurately.

Do not claim that every provider/model was used in the formal evaluation.

For the current formal run state explicitly:

Evaluation provider: DeepSeek
Evaluation model: deepseek-chat

Also document that Groq + openai/gpt-oss-20b is supported if that is true.

Do not claim a Groq evaluation score unless it was actually run.

Do not claim DeepSeek API quota or licensing characteristics that have not
been verified.

============================================================
18. OPEN-SOURCE MODEL REQUIREMENT
============================================================

Be precise in the README.

Do not make an unsupported claim that a hosted API alias automatically proves
a specific licensing status.

Document the exact model/provider used.

If the assignment's "Open Source LLM" requirement needs clarification for the
hosted DeepSeek model, flag that honestly rather than inventing a licensing
claim.

The implementation remains capable of using the intended GPT-OSS model via
Groq once provider quota is available.

Do not let this block completing the rest of the assignment now.

============================================================
19. GROQ LATER, OPTIONAL BEFORE SUBMISSION
============================================================

Do NOT wait for Groq during this phase.

If Groq quota becomes available BEFORE final submission, we may later choose
to run the frozen GPT-OSS verification/evaluation.

That would be a separate measurement.

It must not rewrite or erase the DeepSeek results.

For now, finish the assignment using the available working provider.

============================================================
20. NO OPTIONAL PRODUCT WORK
============================================================

Do not implement:

OCR
image upload
Streamlit
web UI
graph visualization
SVG highlighting
hosting
deployment
authentication
database
vector database
embeddings
new LLM providers

We are finishing the take-home, not expanding it.

============================================================
21. TESTS
============================================================

Before the final documentation commit:

run the complete deterministic suite.

Current baseline:

398 passed
0 failed
4 live deselected

Run the evaluation scoring tests if any are added.

Do not modify production architecture to improve the M3 score.

============================================================
22. GIT
============================================================

Keep real commit history.

Do not squash.

Do not amend historical commits.

Do not fake timestamps.

Do not push yet.

Use the existing Git identity.

No AI attribution in Git metadata.

Secret scan before commits.

.env must remain untracked.

No API keys may enter:

README
eval files
transcripts
prompts
tests
Git history

============================================================
23. COMMITS
============================================================

Use meaningful milestones.

A reasonable structure is:

feat: add graph-grounded evaluation suite

followed by, once actual results exist:

docs: document agent design and evaluation results

Do not force these exact subjects if the actual changes differ.

Do not create many tiny commits for cosmetic edits.

============================================================
24. FINAL VALIDATION
============================================================

Before declaring submission-ready verify:

- fresh clone/install path is documented
- install is one command
- question execution is one command
- required environment variables are documented
- real C01 data is used
- no stand-in graph exists
- visible workflow is shown
- answers are graph-grounded
- missing data is handled honestly
- 15-question eval exists
- scoring script exists
- actual score exists
- 5–10 transcripts exist
- at least two show failures/struggles
- design note is under approximately one page
- limitations are documented
- approximate time spent is documented
- deterministic tests pass
- secret scan passes
- Git working tree is clean
- nothing has been pushed yet

============================================================
25. FINAL REPORT
============================================================

Return:

PROJECT PROGRESS

✓ M1 — Deterministic graph foundation
✓ M2 — Multi-step LLM agent
✓ M2.1 — Agent stabilization
✓ M2.2a — DeepSeek diagnostic
✓ M2.2 final stabilization
✓ M2.2 hygiene
! M2.2b — Groq verification
  Status: provider quota blocked
✓/! M3 — Formal evaluation
  Provider: deepseek
  Model: deepseek-chat
  Score: <actual>
✓/! M4 — Documentation
  Status: <actual>

Then:

A. FROZEN IMPLEMENTATION
- hash

B. EVALUATION DESIGN
- categories
- 15 questions
- scoring method

C. EVALUATION RESULTS
Question | Score | Outcome | Model calls | Tool calls | Tokens | Grounding

D. AGGREGATE SCORE

E. FAILURES / STRUGGLES

F. README CONTENT COMPLETED

G. SETUP REPRODUCIBILITY

H. TEST STATUS

I. SECRET SCAN

J. COMMITS CREATED

K. GIT STATUS

L. REMAINING REQUIREMENT RISKS

M. SUBMISSION READINESS

Then STOP.

Do not push until I explicitly approve it.
