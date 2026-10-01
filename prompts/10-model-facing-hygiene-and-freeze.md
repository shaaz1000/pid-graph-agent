We are continuing the Intuigence AI P&ID graph-agent take-home.

Read the repository, prompt history, current Git history and current
implementation before changing anything.

Current state:

M1
331dd62
feat: add deterministic P&ID graph query layer

M2
c0a881c
feat: add multi-step graph reasoning agent

M2.1
67221a5
fix: improve multi-step graph reasoning stability

Prompt history
5c06f48
docs: preserve assignment and development prompts

Provider portability
9188472
feat: add configurable open-weight LLM provider

DeepSeek provider
e63a83b
feat: add configurable DeepSeek development provider

DeepSeek configuration
308dc59
fix: align DeepSeek environment configuration

Final stabilization
db563eb
fix: preserve traversal boundary evidence

Current deterministic baseline:

398 passed
0 failed
4 live deselected

DeepSeek diagnostic result at 308dc59:

6 correct
1 partially correct
1 correct answer withheld by grounding

The two general issues found by that diagnostic have now been addressed in
db563eb:

1. chamber-boundary graph facts are structured evidence
2. truncated traversal frontiers are distinguished from true terminals

DeepSeek has NOT been rerun, intentionally.

Official Groq verification has NOT been run because the daily quota has not
yet reset.

There is ONE remaining pre-freeze hygiene issue:

The model-facing find_entities description contains concrete C01 examples:

'T4750'
'SV 104.01'
'C5 on line 47126'

We want to remove advance dataset-specific hints before the official
verification.

This instruction supersedes any earlier unsent hygiene instruction.

============================================================
0. SAVE THIS INSTRUCTION
============================================================

Before making changes, save this complete instruction as the next sequential
file under:

prompts/

Use the next available number.

Do not overwrite historical prompt files.

Update prompts/README.md only as necessary to index this new instruction.

Do not alter historical prompt contents.

============================================================
1. REMOVE CONCRETE C01 EXAMPLES
============================================================

Remove concrete C01 entity/identifier examples from MODEL-FACING production
tool descriptions and parameter descriptions.

Specifically remove the current examples:

'T4750'
'SV 104.01'
'C5 on line 47126'

from the find_entities model-facing schema/description.

IMPORTANT:

Do NOT replace them with synthetic identifiers such as:

P1234
V123
SV 001.01
line 10001

or other fabricated examples.

We do not need to teach the model an invented identifier grammar.

Instead describe the capability semantically.

For example, find_entities should communicate approximately:

"Search P&ID graph entities by identifier, type, description, or contextual
description. Context may include information such as an associated line.
Ambiguous matches are exposed rather than guessed."

And its query parameter should communicate approximately:

"Natural-language description or identifier of the entity to find. May
include contextual information such as entity type or associated line."

Adapt wording to the existing schema/style.

Do not mechanically replace existing text if a shorter or clearer semantic
description already exists.

============================================================
2. NARROW MODEL-FACING HINT AUDIT
============================================================

Perform ONE narrow inspection of model-facing production instructions only.

Inspect:

- system prompt
- tool descriptions
- tool parameter descriptions
- other static text sent to the LLM before graph results are returned

Look for concrete C01 facts that could provide advance knowledge of the
evaluation dataset.

Examples worth searching for include:

P4711
P4712
H1007
H1008
T4750
47121
47122
47127
C1
C2
C5
C7
PV4712
TT4750
DN80
"fail close"

This list is for AUDITING only.

Do NOT blindly remove every occurrence from the repository.

The distinction is:

NOT OK:
static model-facing instructions giving the LLM advance knowledge of
specific C01 entities, relationships, properties or answers.

COMPLETELY OK:
those values appearing dynamically in graph/tool results after the model
queries the graph.

Also completely OK:

- deterministic tests
- graph fixtures
- C01 XML
- expected graph facts in tests
- diagnostic transcripts
- historical prompt files
- evaluation records
- implementation comments explaining verified graph behavior where not sent
  to the model

Do not modify those merely because they contain C01 identifiers.

============================================================
3. WHAT TO DO IF ANOTHER MODEL-FACING EXAMPLE IS FOUND
============================================================

If another concrete C01-specific example exists in static model-facing
production text:

remove only the dataset-specific example.

Preserve the generic semantic instruction.

Do NOT redesign the prompt.

Do NOT change tool behavior.

Do NOT replace it with another fabricated identifier.

Report exactly what was removed.

============================================================
4. DO NOT REMOVE NECESSARY DOMAIN SEMANTICS
============================================================

Do NOT over-correct.

Generic P&ID terminology is allowed and necessary.

The model-facing instructions may still discuss concepts such as:

- equipment
- pumps
- valves
- heat exchangers
- instruments
- tags
- line identifiers
- piping
- upstream
- downstream
- adjacency
- reachability
- paths
- properties
- chambers
- instrumentation relationships
- terminal entities
- truncated traversal

Those are domain/tool semantics, not dataset leakage.

Similarly, generic instructions such as:

"get_connections returns immediate adjacency"

"traverse returns downstream or upstream reachability"

"find_path returns a route between entities"

are desirable.

The goal is NOT to make the tool descriptions vague.

The goal is to remove advance knowledge of THIS specific C01 instance.

============================================================
5. DO NOT TOUCH DYNAMIC GRAPH EVIDENCE
============================================================

Real C01 identifiers and values MUST continue to appear in tool results when
they are retrieved from the graph.

For example, if find_entities dynamically returns a real tag, that is correct.

If traverse dynamically returns a real line, equipment item, chamber,
connection or property, that is correct.

If get_properties dynamically returns a real engineering value, that is
correct.

Do not sanitize actual graph evidence.

We are removing static hints, not plant data.

============================================================
6. NO ARCHITECTURE CHANGES
============================================================

This is a hygiene change only.

Do NOT modify:

- DEXPI ingestion
- graph abstraction
- normalizer
- entity resolution behavior
- traversal behavior
- chamber-aware traversal
- boundary evidence
- terminal/frontier semantics
- GraphService
- agent state
- LangGraph workflow
- compaction semantics
- grounding semantics
- instrumentation semantics
- answer synthesis
- turn limits
- tool-call limits
- provider behavior
- error handling

Do not refactor unrelated code.

============================================================
7. DO NOT REOPEN KNOWN LIMITATIONS
============================================================

Do NOT fix:

- slash-joined identifiers such as N1/N2
- instrument-code glossing
- the lack of a deterministic "enough evidence" detector
- redundant but harmless tool calls
- token overhead
- model variance

These are documented limitations.

Do not use this cleanup as an excuse for another stabilization cycle.

============================================================
8. DO NOT RUN DEEPSEEK AGAIN
============================================================

Do NOT rerun the eight DeepSeek diagnostic questions.

The diagnostic phase is finished.

Its purpose was to identify general architectural problems.

It did so.

Those problems were addressed in db563eb.

Running DeepSeek again would turn the diagnostic set into a tuning benchmark.

============================================================
9. TESTING
============================================================

After the model-facing hygiene change, run the complete deterministic suite.

Current baseline:

398 passed
0 failed
4 live deselected

If an existing test asserts the old description string, update only that
assertion.

Do not add unnecessary tests just to increase the test count.

If useful, one narrow assertion that production model-facing schemas contain
no known C01-specific examples is acceptable, but only if it is simple and
maintainable.

Do not build a complicated leakage-detection framework.

============================================================
10. INSPECT THE ACTUAL MODEL-FACING PAYLOAD
============================================================

Before committing, inspect the actual static prompt/tool schema that will be
sent to the model.

Confirm that it teaches:

WHAT the generic graph tools do

without teaching:

WHAT specific entities/answers exist in C01.

Report whether any concrete C01-specific static hints remain.

Do not expose API keys while inspecting payloads.

============================================================
11. SECRET SCAN
============================================================

Before committing:

- inspect git diff
- inspect staged diff
- ensure .env is not staged
- scan for secrets
- ensure no Groq key is present
- ensure no DeepSeek key is present
- ensure no OpenRouter key is present

Never print a discovered secret.

Report only:

secret scan passed

or:

secret scan failed

============================================================
12. COMMIT
============================================================

If tests pass and the diff is limited to this hygiene work, create ONE small
commit.

Suggested subject:

chore: remove dataset-specific tool examples

Do not amend db563eb.

Do not squash commits.

Do not rewrite history.

Do not push.

Use the existing Git identity.

Do not add generated AI attribution to Git metadata.

============================================================
13. FINAL FREEZE POINT
============================================================

After that commit, record its hash.

That commit becomes the FINAL FROZEN IMPLEMENTATION for official M2.2
verification.

From that point until the five Groq questions have completed:

NO source-code changes.

NO prompt changes.

NO tool-description changes.

NO graph changes.

NO grounding changes.

NO traversal changes.

NO compaction changes.

NO provider changes.

NO budget changes.

NO test-driven fixes.

NO DeepSeek runs.

============================================================
14. GROQ QUOTA
============================================================

Do not probe Groq repeatedly.

The previous usage window is expected to release sufficient capacity roughly
24 hours after the heavy usage occurred.

Wait until sufficient capacity is reasonably expected.

Then make ONE minimal capacity check.

If Groq remains rate limited or there is clearly insufficient capacity for
the five-question run:

STOP.

Report:

official verification remains infrastructure blocked

Do not consume partial quota by starting the five-question run.

============================================================
15. OFFICIAL PROVIDER AND MODEL
============================================================

For official M2.2 verification explicitly use:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

Do not use DeepSeek.

Do not use OpenRouter.

Do not automatically fail over.

Do not silently change models.

Before starting record:

git rev-parse HEAD

git status --short

The commit must be the final frozen hygiene commit from this instruction.

The implementation working tree must be clean.

============================================================
16. OFFICIAL FIVE-QUESTION SET
============================================================

Run the already-prepared official M2.2 five-question set.

Do not create new questions.

Do not rewrite existing questions.

Do not modify them based on DeepSeek results.

The frozen set should continue covering:

1. P4712 downstream/discharge/reachability

2. another downstream/reachability formulation using another entity

3. valve/instrumentation/failAction composition

4. another instrumentation relationship formulation

5. H1007 design-pressure grounding regression

Run each question exactly ONCE.

============================================================
17. NO RETRIES
============================================================

No retries for:

incorrect answers
partial answers
grounding rejection
poor wording
unexpected tool choice
extra model calls

If an actual provider/infrastructure failure occurs, classify it separately.

Do not rerun a semantic failure hoping for a better answer.

============================================================
18. NO CHANGES BETWEEN QUESTIONS
============================================================

This is measurement, not development.

If Q1 fails:

record it and continue unchanged.

If Q2 fails:

record it and continue unchanged.

Continue through all five.

Do not patch after any individual result.

============================================================
19. RECORD EVERY RESULT
============================================================

For each question record:

- exact question
- provider
- model
- commit tested
- tool sequence
- tool-call count
- model-call count
- token usage
- latency
- final answer
- grounding pass/fail
- unsupported claims
- fallback used yes/no
- outcome

Outcome must be one of:

correct
partially_correct
incorrect
abstained
infrastructure_failure

Judge correctness using deterministic graph evidence.

Do not classify a provider 429 as an incorrect agent answer.

============================================================
20. Q5-STYLE CHECK
============================================================

For downstream/reachability questions specifically inspect:

- adjacency versus reachability interpretation
- whether traverse was used appropriately
- through_equipment handling
- terminal handling
- truncated frontier handling
- continues_beyond_max_depth handling
- whether multiple meaningful downstream destinations were preserved
- whether the answer overclaimed that a frontier was a final destination
- redundant searches
- turn-limit behavior

Do not require one hard-coded interpretation of "discharge".

If the term is ambiguous, an answer may state its interpretation.

============================================================
21. Q12-STYLE CHECK
============================================================

For the instrumentation/failAction question inspect:

- entity resolution
- line/context resolution
- instrumentation relationship inspection
- whether the related instrumentation entity was followed
- whether failAction was retrieved
- whether "fail close" was supported by graph evidence
- whether the model guessed aliases instead of following relationships
- redundant searches
- turn-limit behavior

Do not require one exact tool sequence.

We care about generic composition.

============================================================
22. Q13-STYLE CHECK
============================================================

For design pressure inspect:

- correct entity
- correct chamber/property attribution
- correct engineering value
- typographic minus handling
- grounding behavior
- regeneration if any

A supported answer must not be rejected merely because of dash/minus
normalization.

============================================================
23. AFTER ALL FIVE
============================================================

Calculate:

- correct count
- partially correct count
- incorrect count
- abstained count
- infrastructure failure count

Also calculate:

- total tokens
- average tokens/question
- total model calls
- average model calls/question
- total tool calls
- average tool calls/question
- turn-limit hits
- grounding regenerations
- fallbacks
- redundant lookups where observable

Do not hide bad results.

Do not rerun anything.

============================================================
24. FREEZE DECISION
============================================================

After reviewing all five results recommend exactly one:

READY_FOR_M3

or

BLOCKING_GENERALIZATION_ISSUE

READY_FOR_M3 does NOT require 5/5.

Ordinary model variance, one imperfect answer, somewhat high token usage or a
documentable edge case are not automatically reasons to reopen development.

Recommend BLOCKING_GENERALIZATION_ISSUE only if the frozen run reveals a
repeatable GENERAL architectural defect likely to materially affect unseen
questions.

Remember the assignment values:

- generalization
- real graph handling
- clean responsibilities
- honest limitations
- good timebox judgement

Do not chase perfection.

============================================================
25. M3 REMAINS LOCKED
============================================================

Even if the five questions are perfect:

DO NOT start M3.

Do not create the formal evaluation set.

Do not run evaluation.

Do not calculate a final score.

Do not start M4.

Wait for my explicit review.

============================================================
26. NO OPTIONAL FEATURES
============================================================

Do not work on:

OCR
image parsing
Streamlit
web UI
graph visualization
SVG highlighting
hosting
deployment
vector database
embeddings
persistent database
authentication
additional LLM providers

These are outside the current requirement.

============================================================
27. FINAL REPORT FORMAT
============================================================

Return:

PROJECT PROGRESS

✓ M1 — Deterministic graph foundation
  Commit: 331dd62

✓ M2 — Multi-step LLM agent
  Commit: c0a881c

✓ M2.1 — Agent stabilization
  Commit: 67221a5

✓ M2.2a — DeepSeek diagnostic
  Commit tested: 308dc59
  Result: 6 correct, 1 partial, 1 grounding-withheld

✓ M2.2 final stabilization
  Commit: db563eb
  Tests before hygiene: 398 passed

✓ M2.2 hygiene
  Commit: <hash>
  Tests: <result>
  Static C01 hints remaining in model-facing instructions: <none / details>

✓/! M2.2b — Official Groq verification
  Commit tested: <hash or not run>
  Provider: groq
  Model: openai/gpt-oss-20b
  Result: <summary / infrastructure blocked>

→ M3 — Formal evaluation
  Recommendation:
  READY_FOR_M3
  or
  BLOCKING_GENERALIZATION_ISSUE
  or
  PENDING_LIVE_VERIFICATION if Groq remains blocked

Then provide:

A. MODEL-FACING HYGIENE
- what was removed
- whether anything else was found
- confirmation that dynamic graph evidence was untouched

B. TEST STATUS
- total
- passed
- failed
- live deselected

C. HYGIENE COMMIT
- hash
- subject

D. FROZEN COMMIT
- exact hash

E. SECRET SCAN
- passed/failed

F. GROQ CAPACITY STATUS

G. OFFICIAL FIVE-QUESTION RESULTS

Question | Outcome | Model calls | Tool calls | Tokens | Grounding

H. Q5-STYLE STATUS

I. Q12-STYLE STATUS

J. Q13-STYLE STATUS

K. EFFICIENCY

L. REMAINING LIMITATIONS

M. GIT STATUS

N. FREEZE RECOMMENDATION

============================================================
28. STOP CONDITION
============================================================

After returning that report:

STOP.

Do not implement fixes.

Do not start M3.

Do not start M4.

Do not push.

Wait for my review.
