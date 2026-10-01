We are continuing the Intuigence AI P&ID agent take-home.

Read the existing repository and current Git history before changing anything.

Current known milestones:

M1
331dd62
feat: add deterministic P&ID graph query layer

M2
c0a881c
feat: add multi-step graph reasoning agent

M2.1
67221a5
fix: improve multi-step graph reasoning stability

Current deterministic baseline:

318 tests passing
4 live tests deselected

Do NOT amend, squash, rebase or rewrite those commits.

Do NOT push anything remotely.

The purpose of this instruction is to:

1. repair prompt history
2. add a clean optional second hosted open-weight LLM provider
3. preserve Groq + GPT-OSS 20B as our primary evaluation baseline
4. verify the M2.1 fixes when Groq quota permits
5. STOP before formal M3 evaluation

Do not expand scope beyond this.

============================================================
0. PERMANENT PROMPT HISTORY RULE
============================================================

Every meaningful engineering instruction I provide from this point onward
must be preserved chronologically under:

prompts/

before implementation begins.

Do NOT overwrite historical prompts.

Do NOT silently edit old prompts.

Do NOT reconstruct missing historical prompts from memory.

Do NOT create prompt files for trivial messages such as:

continue
yes
run tests
show output

Meaningful implementation/design/evaluation instructions should be preserved.

Save THIS entire instruction as:

prompts/06-pre-evaluation-provider-verification.md

If 06 already exists, use the next sequential number and report it.

Prompt files are development provenance.

Do NOT add prompts/ to .gitignore.

Prompt files may naturally contain references to Claude or other tools if
those words were part of the original instruction.

That is historical text and must not be rewritten.

============================================================
1. RESTORE THE AUTHORITATIVE ASSIGNMENT
============================================================

prompts/00-original-assignment.md currently contains an UNAVAILABLE
placeholder.

Replace that placeholder with the exact assignment below.

Do not paraphrase it.

Do not modify its wording.

Do not insert our implementation decisions into it.

Mark it clearly as:

AUTHORITATIVE ASSIGNMENT FROM INTUIGENCE AI

--- BEGIN ORIGINAL ASSIGNMENT ---

Hey Shaaz, it was great speaking with you today! As I mentioned, here's the take home project we'd want you to implement:

**Background**
We build AI engineers for oil & gas plants. Plants are described by P&IDs (piping and instrumentation diagrams). We turn these into knowledge graphs, and an agent answers engineers' questions over them. This exercise is a small version of that.

**The data**
Use pyDEXPI and its reference P&ID:

- pyDEXPI: https://github.com/process-intelligence-research/pyDEXPI
- Reference P&ID (C01): https://github.com/process-intelligence-research/pyDEXPI/blob/master/data/C01V04-VER.EX01.xml
- Graph loader: https://github.com/process-intelligence-research/pyDEXPI/blob/master/pydexpi/loaders/graph_loader.py

pyDEXPI already loads C01 into a NetworkX graph (`ProteusSerializer` → `GraphLoader` / `GraphAbstractor`; see "Graph export" in its README). Build on that graph. Don't hand-write a stand-in dataset. You choose how to abstract or index the graph, but explain the choice.

**The task**
Build an agent that answers natural-language questions about this P&ID as a multi-step workflow. A typical question has two phases:

1. Find the entities the question refers to, whether by tag, type, or description.
2. Traverse the graph from them: neighbours, the pipes between them, paths, and the properties of what it found.

Example questions:

- "What is P4711 connected to, and through which pipes?"
- "Which valves are downstream of the heat exchanger H1007?"
- "What's the nominal diameter of the line between P4711 and H1007?"
- "List every pump and what it feeds."

**These examples are illustrative, not the spec.** When we review, we'll run a set of questions you haven't seen, phrased in different ways. Solutions that map known phrasings to fixed tool calls, in code or in the prompt, won't generalise, and that is the main thing we test.

**Requirements**

- **The workflow must be visible.** For each question, show the steps the agent took (the tool calls and what they returned) as well as the final answer.
- **Answers must be grounded in the graph.** If the data doesn't contain something, say so. Don't make it up.
- **Use an Open Source LLM and framework.** A hosted API is fine. If your solution needs a key, tell us which one and we'll plug ours in.
- **Setup must be simple.** Clone, install, run a question: at most one command each.

**Timebox**
Plan on about 4–6 hours and send it back within 5 days. Tell us roughly how long you spent. We'd rather see a working core and an honest list of what's missing than something polished that took three times as long.

**AI tools**
Use them. This is how we work. We're interested in how you direct them, so keep your real commit history (don't squash it into one commit). If you like, include a few of the prompts or specs that shaped the design.

**What to send**
A link to a GitHub repo containing:

1. The code.
2. A README containing:
   - how to run it
   - a short design note (under a page): your graph abstraction, how the agent plans and traverses, and why
   - 5–10 example transcripts, including at least two where it fails or struggles
3. A small eval: 10–20 questions with expected answers, a script that scores them, and the score you got.
4. Bonus: If you have it hosted somewhere please send that link as well.

**How we'll evaluate**

- It works on questions it wasn't designed for.
- It uses the real graph and handles its messiness.
- The agent design is clean and each part has a clear responsibility.
- You're honest about the limits and the eval measures something real.
- You showed good judgement about what to build in the time you had.

If anything is blocking you, please email me.

Best,
Abdullah

--- END ORIGINAL ASSIGNMENT ---

Do not modify that section after writing it.

============================================================
2. MISSING HISTORICAL M2 PROMPT
============================================================

prompts/04-llm-agent-implementation.md is marked UNAVAILABLE.

Leave it marked UNAVAILABLE.

Do NOT reconstruct it.

Historical accuracy matters more than completeness.

Update the prompts index/README so it truthfully indicates:

00 — exact original assignment
01 — preserved development instruction
02 — preserved development instruction
03 — preserved Git/milestone instruction
04 — original exact instruction unavailable
05 — stabilization instruction
06 — this instruction

Use the actual filenames present in the repository.

============================================================
3. EMPTY WORKING FILE
============================================================

NextImplementationPrompt.md is empty and untracked.

Verify that it is genuinely empty.

If empty, delete it.

Do not commit an empty historical artifact.

Do not add it to .gitignore.

============================================================
4. CURRENT ARCHITECTURE IS APPROVED
============================================================

Do not substantially redesign the deterministic graph layer or LangGraph
workflow.

Keep the current architecture:

C01 DEXPI XML
      ↓
ProteusSerializer
      ↓
DEXPI model
      ↓
GraphLoader
      ↓
plant MultiDiGraph
      ↓
GraphAbstractor
      ↓
conceptual topology
      ↓
normalization / GraphService
      ↓
generic deterministic graph tools
      ↓
LangGraph agent
      ↓
LLM planner
      ↓
graph evidence
      ↓
grounding validation
      ↓
answer + visible execution trace

Keep the current distinction:

CONCEPTUAL GRAPH
for equipment-level piping topology

PLANT GRAPH
for authoritative properties, child/nozzle/chamber facts and provenance

Keep:

- chamber-aware traversal
- open-end provenance
- stable deterministic identifiers
- instrumentation/process-flow separation
- resolved entity state
- adjacency vs reachability vs route semantics
- contextual grounding
- explicit ambiguity
- abstention for missing data

318 deterministic passing tests are the current regression baseline.

============================================================
5. SOURCE-OF-TRUTH PRINCIPLE
============================================================

Maintain this invariant:

THE LLM IS NOT THE SOURCE OF PLANT KNOWLEDGE.

The LLM may:

- interpret natural language
- choose tools
- compose tool calls
- interpret graph results
- formulate the answer

Plant-specific facts must come from deterministic graph evidence.

This includes:

- tags
- equipment identity
- connectivity
- upstream/downstream topology
- line numbers
- segment numbers
- DN values
- engineering properties
- instrumentation relationships
- fail actions
- paths

Unsupported plant facts must not be invented.

============================================================
6. PRIMARY MODEL BASELINE
============================================================

Keep the existing primary configuration:

LLM_PROVIDER=groq

LLM_MODEL=openai/gpt-oss-20b

GROQ_API_KEY=<environment only>

Do NOT replace Groq as the primary evaluation provider.

Do NOT silently switch the existing evaluation baseline to another model.

The live failures we observed came from this provider/model combination, so
the M2.1 verification must eventually use the same combination.

============================================================
7. ADD A SECOND PROVIDER CLEANLY
============================================================

The existing LLM abstraction should support provider replacement.

Add an OPTIONAL second hosted provider adapter using OpenRouter.

The purpose is:

- development fallback
- provider portability demonstration
- avoiding total development blockage when one free provider is rate-limited

It is NOT automatic evaluation failover.

Implement approximately:

LLMClient
├── GroqLLMClient
└── OpenRouterLLMClient

Use the existing protocol/interface rather than duplicating agent logic.

The LangGraph workflow must remain provider-agnostic.

GraphService must remain provider-agnostic.

Grounding must remain provider-agnostic.

Evaluation must remain provider-agnostic.

============================================================
8. OPENROUTER CONFIGURATION
============================================================

Support configuration such as:

LLM_PROVIDER=openrouter
LLM_MODEL=<configured open-weight model>
OPENROUTER_API_KEY=<environment only>

Do not hard-code an API key.

Do not print an API key.

Do not commit an API key.

Do not add a real key to prompt history.

Add only placeholders to:

.env.example

if necessary.

============================================================
9. MODEL REQUIREMENT
============================================================

For this project, only configure/document an OpenRouter fallback model if it
is an open-source/open-weight model appropriate for tool use.

Do NOT choose a proprietary closed model merely because it has a free route.

Do NOT change the formal evaluation model automatically.

If an exact OpenRouter model has not been explicitly configured by me and
cannot be reliably determined from current configuration/documentation:

make the adapter configurable and leave the model configurable.

Do not invent a model identifier.

============================================================
10. NO AUTOMATIC PROVIDER FAILOVER
============================================================

IMPORTANT:

Do NOT implement:

Groq fails
→ automatically use OpenRouter

during an agent run.

Provider selection must be explicit through configuration.

Why:

A formal evaluation must use one fixed model/provider so its score remains
interpretable.

If Groq receives a 429 during evaluation, report:

infrastructure/rate-limit failure

Do not silently reroute the question to another model.

============================================================
11. PROVIDER INTERFACE PARITY
============================================================

Both providers should expose equivalent behavior to the workflow:

- messages
- system instructions
- tool definitions
- tool choice where supported
- structured tool calls
- token usage where available
- provider errors through normalized exceptions/results

Do not leak provider-specific response structures into LangGraph state.

Normalize at the adapter boundary.

============================================================
12. PROVIDER ERROR HANDLING
============================================================

Normalize errors where practical into categories such as:

rate_limit
authentication
provider_unavailable
invalid_request
output_parse_failed
unknown_provider_error

Do not expose secrets inside exception text.

A provider failure must not be mistaken for:

graph not_found

or:

agent abstention.

Infrastructure failures and semantic failures are different categories.

============================================================
13. OPENROUTER TESTS
============================================================

Add deterministic adapter tests using mocks.

Do not require real OpenRouter API access for the normal test suite.

Test at least:

- configuration selection
- missing API key
- request construction
- tool schema forwarding
- tool-call parsing
- ordinary text response
- token usage normalization
- rate-limit normalization
- malformed response
- provider error
- no secret leakage

All ordinary tests must run without network access.

============================================================
14. DO NOT SPEND QUOTA JUST TO PROVE THE ADAPTER
============================================================

Do not make repeated real OpenRouter calls.

If an OpenRouter key is not configured, deterministic mocked tests are enough
for this phase.

If a key is configured, at most one trivial smoke call may be made.

Do not use OpenRouter to replace the pending Groq verification.

============================================================
15. GROQ QUOTA STATUS
============================================================

Before attempting the five targeted Groq questions, determine whether Groq is
still returning the daily-token rate limit.

Do this with the smallest reasonable request or use available provider reset
metadata if exposed.

Do not repeatedly poll.

If the quota is still exhausted:

STOP LIVE VERIFICATION.

Report:

Groq verification blocked by rate limit.

Continue only deterministic/provider work.

Do not burn requests repeatedly.

============================================================
16. M2.1 LIVE VERIFICATION
============================================================

Once Groq quota is available, freeze implementation before starting.

Run the existing five targeted verification questions exactly once each.

Do not patch between them.

Do not retry incorrect answers.

Do not retry until a preferred answer appears.

The set should cover:

1. Q5-style P4712 destination/discharge/reachability

2. another downstream/reachability question with a different entity

3. Q12-style valve → instrumentation → failAction

4. another instrumentation relationship question

5. H1007 design-pressure / grounding regression

Use the existing prepared smoke set if it already satisfies this.

============================================================
17. LIVE RESULT RECORDING
============================================================

For each live question record:

QUESTION
exact text

PROVIDER
Groq

MODEL
openai/gpt-oss-20b

TOOL SEQUENCE
actual calls only

TOOL CALL COUNT

MODEL CALL COUNT

FINAL ANSWER

TOKEN USAGE
if provided

LATENCY
if measured

GROUNDING
pass/fail

UNSUPPORTED CLAIMS

FALLBACK USED
yes/no

OUTCOME
one of:

correct
partially_correct
incorrect
abstained
infrastructure_failure

Do not label a 429 as an incorrect agent answer.

============================================================
18. Q5 VERIFICATION GOAL
============================================================

We previously diagnosed Q5 as:

PLANNING
+
TOOL SEMANTICS
+
ANSWER SYNTHESIS

The stabilized architecture now exposes:

- adjacency
- reachability
- route
- through_equipment
- terminal
- endpoints

Verify whether the real model can now use these generic semantics.

Do not require a special P4712-specific answer.

Do require that if multiple meaningful downstream destinations are present in
the evidence, the model does not falsely present one as though it were the
only possible downstream result.

============================================================
19. Q12 VERIFICATION GOAL
============================================================

We previously diagnosed Q12 as:

TOOL SEMANTICS
+
PLANNING

The graph contains the required:

failAction = fail close

The agent should be capable of composing generic graph operations to reach
it.

A valid conceptual sequence would be:

resolve relevant valve
→ inspect instrumentation relationship
→ follow relevant instrumentation entity
→ inspect property

The exact tool sequence may differ.

Do not create a special-purpose fail-action tool.

============================================================
20. Q13 VERIFICATION GOAL
============================================================

Verify that the H1007 design-pressure answer is no longer rejected because
of typographic dash/minus normalization.

The deterministic validator tests already pass.

This live run is only to ensure the complete agent path behaves correctly.

============================================================
21. TOKEN/CALL EFFICIENCY
============================================================

Record whether M2.1 actually improved live behavior.

Compare with previous observations:

simple:
approximately 1–2 planning/model calls where practical

multi-step:
approximately 2–4 where practical

Do not make these hard correctness requirements.

Report:

- redundant searches
- repeated tool calls
- turn-limit hits
- total model calls
- total tokens

Do not optimize further during the five-question frozen run.

============================================================
22. DO NOT START FORMAL M3 EVAL
============================================================

Even if all five verification questions succeed:

STOP after reporting them.

Do not create the final evaluation questions yet.

I want to review the verification before freezing the architecture.

============================================================
23. PROMPT/PROVIDER COMMIT
============================================================

There are two conceptually distinct changes here:

A. prompt-history repair
B. provider portability

Prefer truthful, coherent commits.

If prompt-history restoration is complete independently, create:

docs: preserve assignment and development prompts

Then, if the OpenRouter adapter is implemented and all tests pass, create:

feat: add configurable open-weight LLM provider

Do NOT manufacture extra commits if the actual change structure makes a
different coherent split more accurate.

Do not amend M1, M2 or M2.1.

============================================================
24. COMMIT QUALITY GATE
============================================================

Before every commit:

- run relevant tests
- run complete deterministic suite before implementation commits
- inspect git diff
- inspect staged diff
- perform secret scan
- ensure .env is not staged
- ensure actual API keys are absent
- ensure no unrelated generated files are staged
- ensure commit message matches actual contents

Do not push.

============================================================
25. GIT ATTRIBUTION RULES
============================================================

Continue using existing Git author identity.

Do not change Git user.name.

Do not change Git user.email.

Do not add generated attribution such as:

Co-Authored-By: Claude
Co-Authored-By: Anthropic
Generated with Claude
Generated by AI
Generated by Copilot

to commit metadata.

Do not add model/provider attribution to commit metadata.

Historical prompts may naturally mention Claude/Opus/Sonnet if those words
were part of the preserved prompt itself.

Do not alter historical prompt text.

============================================================
26. SECRET RULES
============================================================

Never commit:

.env

GROQ_API_KEY actual value

OPENROUTER_API_KEY actual value

gsk_ tokens

OpenRouter tokens

or any other credentials.

.env.example may contain variable names with blank/example values.

Before each commit report only:

secret scan: passed

or:

secret scan: failed

Never print the discovered secret.

============================================================
27. TEST BASELINE
============================================================

Current baseline:

318 deterministic tests passing.

Provider work must not regress the graph/agent layer.

After provider implementation run the full suite.

Report:

previous test count
new test count
passed
failed
deselected live tests

Do not treat an increased test count as a goal by itself.

Quality and generalization matter more than quantity.

============================================================
28. NO QUESTION-SPECIFIC HACKS
============================================================

Continue enforcing:

No:

if "P4712" ...
if "H1007" ...
if "discharge" then fixed sequence
if "fail action" then fixed sequence

No fixed mappings for Abdullah's example questions.

No special tools designed solely to pass known questions.

Tool behavior must remain generic.

============================================================
29. NO OPTIONAL PRODUCT FEATURES
============================================================

Do not work on:

OCR
Streamlit
web UI
SVG visualization
graph highlighting
hosting
deployment

Do not add a database.

Do not add a vector database.

Do not add embeddings unless a demonstrated requirement appears.

The current 36-entity conceptual graph does not justify that complexity.

============================================================
30. FORMAL EVALUATION PRINCIPLE
============================================================

When M3 eventually begins, the formal evaluation must remain meaningfully
independent from development.

The process will be:

development failures
↓
general stabilization
↓
targeted verification
↓
architecture freeze
↓
create 10–20 question evaluation
↓
run once
↓
report actual score
↓
document failures honestly

Do not secretly tune against final eval questions.

============================================================
31. README IS NOT FINAL YET
============================================================

Do not turn this phase into the final README/documentation phase.

Only update documentation required to explain:

- prompt history
- provider configuration

if necessary.

The complete README belongs to M4.

Do not invent:

evaluation score
final transcripts
final time spent

before those exist.

============================================================
32. CURRENT ACTION ORDER
============================================================

Execute in this order:

STEP 1
Save this prompt under prompts/.

STEP 2
Restore the exact original assignment into
prompts/00-original-assignment.md.

STEP 3
Update the prompt-history index truthfully.

STEP 4
Delete the empty untracked NextImplementationPrompt.md after verifying it is
empty.

STEP 5
Run current tests and confirm the 318-test baseline.

STEP 6
Create the prompt-history documentation commit if appropriate:

docs: preserve assignment and development prompts

STEP 7
Inspect the existing LLM abstraction.

STEP 8
Implement the OpenRouter adapter without modifying agent semantics.

STEP 9
Add mocked deterministic provider tests.

STEP 10
Run the entire deterministic test suite.

STEP 11
Create provider commit if everything passes:

feat: add configurable open-weight LLM provider

STEP 12
Check whether Groq quota is available using the smallest reasonable request
or reset metadata.

STEP 13A
If still rate limited:
do NOT retry.
Report the block.

STEP 13B
If available:
freeze code and run the five targeted Groq verification questions once each.

STEP 14
Report everything below.

STEP 15
STOP.

Do NOT start M3.

============================================================
33. FINAL REPORT FORMAT
============================================================

Return:

PROJECT PROGRESS

✓ M1 — Deterministic graph foundation
  Commit: 331dd62
  Status: complete

✓ M2 — Multi-step LLM agent
  Commit: c0a881c
  Status: complete

✓ M2.1 — Agent stabilization
  Commit: 67221a5
  Tests: 318 baseline
  Status: complete

✓/! M2.2 — Provider + live verification
  Status: <status>

→ M3 — Formal evaluation
  Status: waiting for review

○ M4 — CLI + documentation
  Status: pending

○ Bonus
  Status: not started

Then report:

1. PROMPT HISTORY
   - files present
   - exact vs unavailable
   - documentation commit hash

2. PROVIDER ARCHITECTURE
   - interface
   - Groq adapter
   - OpenRouter adapter
   - configuration
   - error normalization

3. TEST RESULTS
   - total
   - passed
   - failed
   - live deselected

4. PROVIDER COMMIT
   - hash
   - subject

5. GROQ QUOTA STATUS

6. FIVE LIVE VERIFICATION RESULTS
   - or clearly state they remain blocked

7. Q5 STATUS

8. Q12 STATUS

9. Q13 STATUS

10. TOKEN/MODEL CALL OBSERVATIONS

11. REMAINING KNOWN LIMITATIONS

12. GIT STATUS

13. SECRET SCAN STATUS

14. RECOMMENDATION
   - whether architecture is ready to freeze for M3

============================================================
34. STOP CONDITION
============================================================

STOP after the report.

Do not begin formal evaluation.

Do not make additional architecture changes after the five-question live run.

Wait for my review.

============================================================
35. CORE INVARIANTS
============================================================

Keep these principles throughout:

THE REAL C01 DEXPI GRAPH IS THE DATA SOURCE.

DO NOT HAND-WRITE A SUBSTITUTE DATASET.

THE LLM PLANS; IT DOES NOT INVENT PLANT KNOWLEDGE.

GRAPH OPERATIONS ARE DETERMINISTIC.

ANSWERS MUST BE SUPPORTED BY GRAPH EVIDENCE.

MISSING INFORMATION MUST BE REPORTED AS MISSING.

AMBIGUITY MUST NOT BE SILENTLY RESOLVED.

FUZZY SUGGESTIONS ARE NOT AUTHORITATIVE MATCHES.

INSTRUMENTATION RELATIONSHIPS ARE NOT PROCESS FLOW.

OPEN ENDS ARE NOT FABRICATED DESTINATIONS.

DIRECT ADJACENCY IS NOT THE SAME AS REACHABILITY.

REACHABILITY IS NOT THE SAME AS A SPECIFIC PATH.

CURRENT FLOW CANNOT BE INFERRED FROM TOPOLOGY WITHOUT OPERATING STATE.

VISIBLE WORKFLOW MEANS REAL TOOL CALLS AND RESULTS, NOT HIDDEN
CHAIN-OF-THOUGHT.

THE FOUR EXAMPLE QUESTIONS ARE ILLUSTRATIVE, NOT THE SPEC.

DO NOT OVERFIT TO KNOWN QUESTIONS.

KEEP REAL COMMIT HISTORY.

KEEP CHRONOLOGICAL PROMPT HISTORY.

KEEP SECRETS OUT OF GIT.

DO NOT SILENTLY SWITCH MODELS DURING EVALUATION.

KEEP THE SOLUTION WITHIN THE SPIRIT OF A 4–6 HOUR TAKE-HOME.

Correctness, generalization, grounding and engineering judgement matter more
than feature count.
