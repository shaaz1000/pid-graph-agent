We are continuing the Intuigence AI P&ID graph-agent take-home.

Before doing anything, read:

- prompts/00-original-assignment.md
- prompts/README.md
- prompts/05-agent-stabilization.md
- prompts/06-pre-evaluation-provider-verification.md
- current Git history
- current implementation

Current milestones:

M1
331dd62
feat: add deterministic P&ID graph query layer

M2
c0a881c
feat: add multi-step graph reasoning agent

M2.1
67221a5
fix: improve multi-step graph reasoning stability

Prompt-history repair
5c06f48
docs: preserve assignment and development prompts

Provider portability
9188472
feat: add configurable open-weight LLM provider

Current deterministic baseline:

351 tests passing
4 live tests deselected

Current problem:

Groq + openai/gpt-oss-20b is our intended official verification/evaluation
configuration, but Groq's 200k-token rolling daily quota is currently blocking
the five-question M2.2 live verification.

I have access to DeepSeek separately.

We will use DeepSeek ONLY as a temporary development/diagnostic provider while
waiting for Groq capacity.

We will then switch back to:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

for the official frozen M2.2 verification and M3 evaluation.

Do NOT begin M3 in this instruction.

============================================================
0. SAVE THIS PROMPT FIRST
============================================================

Before implementation, save this complete instruction as the next sequential
file under:

prompts/

For example:

prompts/07-deepseek-diagnostic-verification.md

Use the next available number if 07 already exists.

Do not overwrite historical prompts.

Do not modify the authoritative original assignment.

Do not create a separate commit solely for this prompt yet unless needed for
a coherent milestone.

============================================================
1. FIRST PRINCIPLE
============================================================

DeepSeek is NOT replacing the submission/evaluation model.

It is a temporary diagnostic model.

The intended process is:

current architecture
        ↓
DeepSeek diagnostic testing
        ↓
identify GENERAL failures only
        ↓
fix only genuine architecture/tool/grounding bugs if necessary
        ↓
deterministic regression tests
        ↓
freeze implementation
        ↓
switch configuration back to Groq
        ↓
openai/gpt-oss-20b
        ↓
5-question M2.2 verification ONCE
        ↓
review
        ↓
M3 formal evaluation later

Do not mix DeepSeek results with Groq results.

Every live transcript/result must explicitly identify:

provider
model

============================================================
2. DO NOT ADD MORE PROVIDERS
============================================================

We currently have:

LLMClient
├── GroqProvider
└── OpenRouterProvider

We may add:

DeepSeekProvider

because I already have DeepSeek access and it solves the immediate development
blocker.

Do NOT add:

Ollama
Cerebras
Together
Fireworks
Hugging Face
LM Studio
or any other provider in this phase.

Do not spend time searching for "unlimited free APIs".

That is now outside scope.

We have enough provider infrastructure.

============================================================
3. DEEPSEEK KEY HANDLING
============================================================

Use:

DEEPSEEK_API_KEY

from the environment.

Never print it.

Never include it in logs.

Never commit it.

Never put the real value into:

.env.example
tests
prompts
README
fixtures
snapshots
Git history

If configuration documentation is needed:

DEEPSEEK_API_KEY=

is sufficient.

If the key is not currently configured, STOP before making live calls and tell
me exactly which environment variable I need to populate.

Do NOT ask me to paste the secret into chat.

============================================================
4. DEEPSEEK PROVIDER IMPLEMENTATION
============================================================

First inspect whether the current provider abstraction can support DeepSeek
cleanly.

If a dedicated adapter is necessary, implement:

DeepSeekProvider

behind the EXISTING LLMClient interface.

Do not modify LangGraph semantics merely to support DeepSeek.

Do not modify graph tools.

Do not modify GraphService.

Do not modify traversal.

Do not modify grounding merely to accommodate provider-specific output.

Normalize provider-specific behavior at the adapter boundary.

The agent should continue to call something equivalent to:

LLMClient.complete(
    messages,
    tools,
    tool_choice
)

and receive the existing normalized LLMResponse.

============================================================
5. KEEP PROVIDER SELECTION EXPLICIT
============================================================

Support explicit configuration:

DEVELOPMENT:

LLM_PROVIDER=deepseek
LLM_MODEL=<configured DeepSeek model>

OFFICIAL VERIFICATION:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

Do NOT implement automatic fallback.

Never do:

Groq 429
→ DeepSeek

or:

DeepSeek failure
→ OpenRouter

inside an agent run.

One run = one explicitly selected provider/model.

============================================================
6. DO NOT INVENT THE DEEPSEEK MODEL
============================================================

Inspect the existing local configuration/environment.

If DEEPSEEK_MODEL or LLM_MODEL is already configured for my DeepSeek usage,
use that.

If the model is not configured, do NOT guess a model identifier.

Tell me what configuration is missing.

The adapter should remain model-configurable.

============================================================
7. DEEPSEEK ADAPTER TESTS
============================================================

If a new adapter is required, add deterministic mocked tests covering the
important provider-boundary behavior.

At minimum verify:

- provider selection
- missing key
- request construction
- model configuration
- messages
- tool definitions
- tool-call parsing
- ordinary text response
- token-usage normalization where available
- malformed response
- rate-limit/error normalization
- secret redaction
- no automatic provider failover

Do not inflate the test count for its own sake.

Use the smallest useful set of tests.

Run the complete deterministic suite afterward.

351 passing tests is the pre-change baseline.

============================================================
8. ARCHITECTURE INVARIANTS
============================================================

Do not change these unless the diagnostic run demonstrates a genuine general
failure.

The real C01 DEXPI graph is the plant-data source.

The LLM interprets and plans.

Deterministic graph tools execute graph operations.

Plant facts come from graph evidence.

Grounding prevents unsupported claims.

Ambiguity is exposed rather than guessed.

Missing data causes an honest missing-data answer.

Instrumentation relationships are not process flow.

Open ends are not fabricated destinations.

Direct adjacency is not reachability.

Reachability is not a specific route/path.

Conceptual graph is used for equipment-level topology.

Plant graph is used for authoritative detailed properties/provenance.

Chamber-aware traversal remains enabled.

Recovered open ends retain explicit provenance.

No vector database.

No embeddings.

No hand-written replacement dataset.

============================================================
9. NO QUESTION-SPECIFIC LOGIC
============================================================

Absolutely do not introduce logic such as:

if P4712 ...
if H1007 ...
if line 47127 ...
if question contains "discharge" ...
if question contains "fail action" ...
if question contains "design pressure" ...

Do not create:

get_pump_discharge()
get_fail_action_for_valve()
answer_h1007_pressure()

or equivalent special-purpose tools.

The assignment explicitly tests unseen wording.

Any fix must improve a general class of questions.

============================================================
10. DEEPSEEK DIAGNOSTIC PHASE
============================================================

Once the adapter works and deterministic tests pass, use DeepSeek for a small
diagnostic run.

This is NOT the formal evaluation.

This is NOT the official M2.2 verification.

The goal is to determine whether the stabilized generic architecture behaves
sensibly with a real LLM.

Start with the same failure classes that motivated M2.1:

A. downstream/reachability semantics

B. instrumentation relationship composition

C. grounded property answer / design-pressure validation

============================================================
11. DIAGNOSTIC QUESTION SET
============================================================

Use the existing targeted questions where useful, BUT also use paraphrases and
different entities so that we do not merely tune against Q5 and Q12.

Keep the diagnostic set small.

Maximum:

8 live DeepSeek questions.

Suggested structure:

2 downstream/reachability questions
2 instrumentation questions
1 property/grounding question
1 ambiguity question
1 missing-data question
1 ordinary simple connectivity question

At least half of the questions must NOT be literal copies of previously failed
questions.

Where possible use different entities from the original failures.

Do not build a giant test suite.

============================================================
12. RECORD DEEPSEEK RESULTS
============================================================

For every DeepSeek diagnostic question record:

- exact question
- provider
- model
- tool sequence
- tool-call count
- model-call count
- final answer
- token usage if available
- latency if available
- grounding result
- unsupported claims
- fallback usage
- outcome

Outcome:

correct
partially_correct
incorrect
abstained
infrastructure_failure

Use deterministic graph evidence when judging correctness.

============================================================
13. CLASSIFY FAILURES BEFORE TOUCHING CODE
============================================================

For every incorrect or partially correct result, classify the root cause BEFORE
changing anything.

Use:

PLANNING

TOOL_SEMANTICS

ENTITY_RESOLUTION

GRAPH_LIMITATION

COMPACTION

STATE_REUSE

ANSWER_SYNTHESIS

GROUNDING

PROVIDER_FORMATTING

MODEL_VARIANCE

INFRASTRUCTURE

or another clearly justified category.

Do not modify code until the failure is understood.

============================================================
14. WHAT COUNTS AS A BLOCKING GENERAL ISSUE
============================================================

Examples of legitimate architecture problems:

- tool results omit information required to answer a broad class of questions
- instrumentation links cannot be followed generically
- resolved entities repeatedly collapse into aliases incorrectly
- graph evidence exists but grounding systematically rejects it
- compaction removes destinations/path facts required for reasoning
- provider adapter corrupts tool calls
- agent loops despite already-resolved entities because state reuse is broken
- graph traversal itself returns incorrect topology

These may justify a fix.

============================================================
15. WHAT DOES NOT JUSTIFY MORE ENGINEERING
============================================================

Do NOT modify architecture merely because:

- DeepSeek phrases an answer awkwardly
- one run uses an unnecessary tool call
- one answer is slightly verbose
- one answer is conservative but correct
- token usage is somewhat high
- one model chooses a different valid route
- temperature 0 still produces model variance
- the answer could be prettier
- a known graph limitation is honestly disclosed
- a model occasionally needs an extra planning step

This is a 4–6 hour take-home exercise.

We are not building a production refinery platform.

============================================================
16. VERY IMPORTANT: LIMIT THE TUNING LOOP
============================================================

Do not repeatedly:

run question
→ patch prompt
→ rerun same question
→ patch prompt
→ rerun

That would overfit.

Instead:

Run the initial diagnostic batch.

Analyze ALL results.

If no blocking general issue exists:

MAKE NO AGENT CHANGES.

If a blocking general issue exists:

identify the smallest general fix.

Add deterministic regression coverage.

Implement the fix ONCE.

Run the deterministic suite.

Then run at most ONE small confirmation set using paraphrased/different
questions.

Maximum DeepSeek live diagnostic rounds:

2.

After that, STOP tuning.

============================================================
17. Q5 CLASS OF BEHAVIOR
============================================================

For downstream/reachability questions, inspect whether the agent understands
the distinction between:

adjacent equipment

versus

entities reachable downstream

versus

a path to a specific target

The current graph/tool layer exposes:

through_equipment
terminal
endpoints
distance/path information

The model should use these generic facts.

Do not encode a fixed meaning for "feeds" or "discharge".

If terminology is ambiguous, a good answer may state the interpretation.

What is unacceptable:

evidence contains several meaningful downstream destinations but the answer
asserts one is the only destination without qualification.

============================================================
18. Q12 CLASS OF BEHAVIOR
============================================================

For instrumentation questions, verify that the model can generically compose:

entity resolution
→ instrumentation relationship inspection
→ related instrumentation entity
→ property retrieval

It should not need to guess identifier variants repeatedly.

The relationship metadata should tell the model what the link means.

Do not add a hard-coded instrumentation chain.

============================================================
19. Q13 CLASS OF BEHAVIOR
============================================================

For graph-supported engineering properties:

retrieve the value
→ preserve property attribution
→ ground the claim
→ answer

Verify that typographic differences such as:

-
–
—

do not create false unsupported-claim failures.

Do not loosen grounding globally merely to make answers pass.

============================================================
20. STOPPING BEHAVIOR
============================================================

We already know there is no perfect deterministic "enough evidence" detector.

Do not attempt to build an elaborate sufficiency engine.

Observe whether the existing combination of:

resolved state
duplicate-call detection
prompt instruction
iteration limit

keeps unnecessary continuation bounded.

If yes, accept the limitation.

============================================================
21. TOKEN USAGE
============================================================

Measure token usage during DeepSeek diagnostics if the API exposes it.

The purpose is observation, not optimization.

We already know the fixed prompt/tool-schema overhead is substantial.

Do not redesign the entire tool API merely to shave tokens.

Correctness and generalization matter more than token minimization for this
take-home.

============================================================
22. AFTER DEEPSEEK DIAGNOSTICS
============================================================

Once DeepSeek diagnostics are satisfactory:

STOP DEVELOPMENT.

Do not continue adding features.

The next stage is official verification with:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

No DeepSeek result should be substituted for that verification.

============================================================
23. GROQ CAPACITY
============================================================

Do not repeatedly probe Groq.

The previous report indicates the rolling token window should release the
large usage roughly 24 hours after it was consumed.

When sufficient Groq capacity is expected, make ONE minimal capacity check.

If still blocked:

wait.

Do not burn partial quota attempting multi-turn questions.

============================================================
24. OFFICIAL M2.2 VERIFICATION
============================================================

When Groq has sufficient capacity:

FREEZE CODE FIRST.

Record:

git rev-parse HEAD

git status --short

Then configure:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

Run the existing five-question targeted verification set exactly ONCE.

No retries.

No changes between questions.

No prompt edits.

No tool edits.

No graph edits.

No grounding edits.

No budget changes.

No model switching.

============================================================
25. FIVE OFFICIAL QUESTIONS
============================================================

Use the already-prepared frozen verification set covering:

1. P4712 downstream/discharge/reachability

2. another downstream/reachability formulation with another entity

3. line-47127 valve → instrumentation → failAction

4. another instrumentation relationship formulation

5. H1007 design-pressure grounding regression

Do not rewrite the questions after seeing DeepSeek's answers.

DeepSeek diagnostics must not alter the official frozen questions.

============================================================
26. OFFICIAL RESULT RECORDING
============================================================

For each Groq question record:

exact question

provider:
groq

model:
openai/gpt-oss-20b

tool sequence

tool-call count

model-call count

token usage

latency

final answer

grounding result

unsupported claims

fallback used

outcome

Use:

correct
partially_correct
incorrect
abstained
infrastructure_failure

Never classify a 429 as an agent correctness failure.

============================================================
27. AFTER THE FIVE GROQ QUESTIONS
============================================================

Do NOT fix anything immediately.

First report the entire frozen run.

Calculate:

correct count
partially correct count
incorrect count
abstained count
infrastructure failures

total tokens
average tokens/question

total model calls
average model calls/question

total tool calls
average tool calls/question

turn-limit hits

redundant lookup count where observable

============================================================
28. FREEZE DECISION
============================================================

At the end recommend exactly one:

READY_FOR_M3

or

BLOCKING_GENERALIZATION_ISSUE

READY_FOR_M3 does NOT require 5/5.

Recommend READY_FOR_M3 if:

- graph operations are generally correct
- agent composes tools reasonably
- answers remain grounded
- ambiguity/missing data are handled honestly
- any remaining failures look like ordinary model limitations or documented
  edge cases

Recommend BLOCKING_GENERALIZATION_ISSUE only if:

- there is a repeatable general architectural flaw
- it is likely to affect unseen questions
- it cannot reasonably be documented as a limitation

Do not chase perfection.

============================================================
29. M3 REMAINS LOCKED
============================================================

DO NOT:

create final evaluation questions

run formal evaluation

calculate final score

write final evaluation transcripts

tune against final evaluation

during this instruction.

M3 begins only after my explicit approval.

============================================================
30. COMMITS
============================================================

If adding DeepSeekProvider is necessary and implementation/tests are complete,
make one coherent commit.

Suggested:

feat: add configurable DeepSeek development provider

Include the relevant prompt-history file if appropriate and truthful.

If a genuine general agent fix is required after diagnostics, make that a
SEPARATE commit.

Suggested:

fix: improve general agent reasoning behavior

Only use that message if it accurately describes the change.

Do not manufacture commits.

Do not amend existing commits.

Do not rewrite history.

Do not push.

============================================================
31. GIT RULES
============================================================

Use the existing Git identity.

Do not change user.name.

Do not change user.email.

No generated attribution in Git metadata.

Do not add:

Co-Authored-By: Claude
Co-Authored-By: Anthropic
Generated by AI
Generated with Claude
Generated with Copilot

Historical prompt text is exempt when those words genuinely appeared in the
original instruction.

============================================================
32. SECRET SCAN
============================================================

Before every commit:

inspect git diff

inspect staged diff

run relevant tests

run complete deterministic suite for implementation changes

perform secret scan

ensure .env is not staged

ensure no actual Groq/OpenRouter/DeepSeek key is present

Never print discovered secret values.

Report only:

secret scan passed

or

secret scan failed

============================================================
33. DO NOT ADD OPTIONAL FEATURES
============================================================

Still do NOT implement:

OCR
image parsing
Streamlit
web UI
SVG highlighting
graph visualization
hosting
deployment
vector database
embeddings
persistent database
authentication

None of these solve our current problem.

============================================================
34. README
============================================================

Do not write the final README yet.

Only make minimal provider/config documentation changes if required.

M4 will contain the final:

setup
run instructions
design note
example transcripts
evaluation results
limitations
time spent

Do not invent any of those results now.

============================================================
35. IMPORTANT SUBMISSION STORY
============================================================

Preserve this architecture story:

"The LLM interprets intent and plans graph operations; it is not the source
of plant knowledge. All factual answers are derived from deterministic
operations over the pyDEXPI graph."

Provider portability is secondary.

Do not let the repository look like an LLM-provider integration exercise.

The important engineering work is:

DEXPI ingestion
graph abstraction
entity resolution
generic graph operations
multi-step planning
visible workflow
grounding
evaluation

============================================================
36. TIMEBOX DISCIPLINE
============================================================

We are already beyond the point where adding more architecture automatically
improves the submission.

From this point forward:

prefer measurement over implementation.

prefer documented limitations over speculative fixes.

prefer generic fixes over question-specific fixes.

prefer a frozen honest evaluation over repeated tuning.

The goal is now to prove the architecture, evaluate it honestly, document it,
and submit it.

============================================================
37. EXECUTION ORDER
============================================================

Execute in this exact order:

1. Save this prompt.

2. Inspect current Git status/history.

3. Inspect existing LLM abstraction.

4. Determine whether a small DeepSeek adapter is required.

5. If required, implement it without touching agent semantics.

6. Add minimal mocked adapter tests.

7. Run complete deterministic suite.

8. Secret scan.

9. Commit provider work if appropriate.

10. If DeepSeek credentials/model are configured, run diagnostic batch 1,
    maximum 8 questions.

11. Analyze all diagnostic failures before modifying anything.

12. If there is NO blocking general issue:
    do not change agent code.

13. If there IS a blocking general issue:
    implement ONE smallest general correction,
    add regression tests,
    run deterministic suite,
    and optionally run ONE small confirmation batch.

14. Stop DeepSeek tuning.

15. When sufficient Groq quota becomes available, freeze implementation.

16. Run the five official Groq M2.2 questions exactly once.

17. Record complete results.

18. Recommend READY_FOR_M3 or BLOCKING_GENERALIZATION_ISSUE.

19. STOP.

Do not begin M3.

============================================================
38. FINAL REPORT
============================================================

Return:

PROJECT PROGRESS

✓ M1 — Deterministic graph foundation
  Commit: 331dd62

✓ M2 — Multi-step LLM agent
  Commit: c0a881c

✓ M2.1 — Agent stabilization
  Commit: 67221a5

✓ M2.2a / ! M2.2a — DeepSeek diagnostics
  Provider: <provider>
  Model: <model>
  Result: <summary>

✓ M2.2b / ! M2.2b — Official Groq verification
  Provider: groq
  Model: openai/gpt-oss-20b
  Commit tested: <hash>
  Result: <summary>

→ M3 — Formal evaluation
  Recommendation:
  READY_FOR_M3
  or
  BLOCKING_GENERALIZATION_ISSUE

Then provide:

A. PROVIDER CHANGES
- files
- tests
- commit

B. DETERMINISTIC TEST STATUS
- previous count
- current count
- passed
- failed

C. DEEPSEEK DIAGNOSTIC RESULTS

Question | Outcome | Model calls | Tool calls | Tokens | Grounding

D. GENERAL ISSUES FOUND

E. FIXES MADE
or:
none

F. OFFICIAL GROQ RESULTS

Question | Outcome | Model calls | Tool calls | Tokens | Grounding

G. Q5 STATUS

H. Q12 STATUS

I. Q13 STATUS

J. EFFICIENCY
- tokens
- calls
- redundant operations
- turn-limit behavior

K. REMAINING LIMITATIONS

L. SECRET SCAN

M. GIT STATUS

N. FREEZE RECOMMENDATION

============================================================
39. FINAL STOP CONDITION
============================================================

After returning the report:

STOP.

Do not start M3.

Do not create evaluation questions.

Do not add features.

Do not make additional fixes unless I explicitly approve them.
