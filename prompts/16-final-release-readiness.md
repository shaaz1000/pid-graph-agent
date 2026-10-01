FINAL RELEASE READINESS — INTUIGENCE AI TAKE-HOME

We are at the final release stage for the Intuigence AI take-home assignment from Abdullah Jibaly.

Repository:
https://github.com/shaaz1000/pid-graph-agent

Current branch:
main

The repository is already public and has already been pushed.

IMPORTANT:
This is NOT another implementation milestone.
Do not redesign the architecture.
Do not add features unless required to fix a genuine release blocker discovered below.

The goal is:

AUDIT → LIVE SMOKE TEST → FIX RELEASE ISSUES ONLY → VERIFY → PUSH → FREEZE

After this, the repository should be ready to send to Abdullah.

==================================================
0. ORIGINAL ASSIGNMENT IS THE SOURCE OF TRUTH
==================================================

First read:

prompts/00-original-assignment.md

Then read:

README.md
docs/SUBMISSION_AUDIT.md
docs/HOW_IT_WORKS.md
docs/ARCHITECTURE_DEEP_DIVE.md
docs/DEMO_SCRIPT.md
prompts/README.md

Map the final repository against EVERY explicit requirement in Abdullah's original assignment.

Do not rely only on our previous audit.

Verify the implementation itself.

The required deliverables are:

1. Code.
2. README containing:
   - how to run
   - short design note under roughly a page
   - graph abstraction
   - how the agent plans/traverses
   - why those decisions were made
   - 5–10 example transcripts
   - at least two examples where it fails or struggles
3. Evaluation:
   - 10–20 questions
   - expected answers
   - scoring script
   - score obtained
4. Visible workflow:
   - tool calls
   - tool results
   - final answer
5. Answers grounded in the graph.
6. Missing information must not be invented.
7. Open-source/open-weight LLM and framework.
8. Simple setup.
9. Real commit history.
10. Rough time spent.
11. Optional hosted version.

Also verify that the solution genuinely uses:

ProteusSerializer
→ GraphLoader
→ GraphAbstractor

on the real C01 P&ID and not a stand-in dataset.

==================================================
1. VERIFY CURRENT GROUNDING IMPLEMENTATION
==================================================

The repository recently moved from primarily token/lexical grounding to structured claim-level grounding.

Audit the implementation carefully.

The intended authority chain is:

real pyDEXPI graph
→ deterministic graph tools
→ typed graph facts/evidence
→ structured answer claims
→ deterministic claim validation
→ natural-language answer

The LLM must NEVER itself become the authority for plant facts.

Verify that:

A. Facts are built only from authoritative graph tool results.

B. User question text does not become plant evidence.

C. Tool input arguments do not become plant evidence.

D. Warnings do not become plant evidence.

E. Fuzzy suggestions do not become resolved entities.

F. Claims validate the correct:
   - subject
   - predicate/property
   - object/value
   - unit
   - relationship
   - direction where applicable
   - provenance

G. A matching number/string elsewhere in the graph cannot validate a claim about the wrong object.

H. DN 80, 80 mm, 80 bar, 80 °C, and plain 80 remain semantically distinct unless an explicitly tested deterministic conversion exists.

I. An unsupported factual claim cannot survive merely because its words appear somewhere in evidence.

J. The secondary token-level check is restrictive only. It must not be able to establish factual truth that failed structured validation.

K. Final prose cannot freely append additional unsupported plant facts outside validated claims.

L. False premises from the user are graph-checked.

M. Absence is phrased conservatively:
   "not represented/present in the loaded P&ID/graph"
rather than claiming something physically does not exist in the real plant.

N. P&ID topology is not represented as live process state.

If there is a genuine hole in any of these invariants, fix the smallest possible thing necessary.

Do not introduce:
- embeddings
- vector DB
- BM25
- Neo4j
- second LLM judge
- external guardrails framework
- policy engine
- another database
- new infrastructure

==================================================
2. LIVE SMOKE TEST THE NEW GROUNDING
==================================================

This is important because the structured claim architecture was added after the saved formal evaluation.

Do NOT rerun the full 15-question formal evaluation.

Do NOT overwrite or modify the historical evaluation artifacts.

Run these seven questions ONCE against the CURRENT agent using the configured open-weight GPT-OSS provider if provider quota permits:

1.
What is P4711 connected to, and through which pipes?

2.
Which pumps are upstream of H1008?

3.
Trace the route from H1007 to T4750 and give me the line number and pipe size.

4.
What is the nominal diameter at component C1?

5.
How much does H1007 weigh?

6.
Since H1008 is rated for 500 kW, which line feeds it?

7.
For control loop 4712.02, where is pressure sensed and which valve does it ultimately act on?

For EACH question report:

- provider
- model
- answer
- tools called
- structured claims emitted
- claim validation result
- grounding status
- whether regeneration occurred
- whether fallback occurred
- whether any unsupported factual prose survived

The purpose is NOT to create another benchmark.

It is only a post-hardening live smoke test proving that the model can actually use the new structured claims protocol.

Do not modify prompts or code merely to make these seven exact questions pass.

If a failure reveals a GENERAL bug, diagnose it and fix the general mechanism.

Never introduce question-specific routing or known-answer mappings.

If Groq cannot run because of quota/provider availability:

- do not substitute historical answers
- do not fabricate results
- report the infrastructure limitation
- continue all deterministic release checks

If another already-configured provider is used for diagnostic purposes, label it accurately.

==================================================
3. FIX STALE SUBMISSION AUDIT
==================================================

docs/SUBMISSION_AUDIT.md currently contains stale pre-publication statements.

Fix them.

The repository IS already public:

https://github.com/shaaz1000/pid-graph-agent

Remove/update statements such as:

- "GitHub repo link: Not done yet"
- "No remote is configured"
- "nothing has been pushed"
- "repository still has to be pushed"

Verify the actual remote before writing anything.

Also update the prompt history count.

prompts/15-structured-claim-grounding.md now exists.

Do not claim prompts/00–14 if 15 exists.

Re-read the entire audit for any other stale statements caused by:

- repository publication
- UI addition
- structured grounding
- test count changes
- later documentation changes

The audit must describe CURRENT repository state.

==================================================
4. LICENSING AUDIT
==================================================

The project directly depends on pyDEXPI.

Check the actual upstream pyDEXPI license and the obligations relevant to distributing this repository.

Do not guess.

Inspect:
- pyDEXPI upstream license
- dependency metadata if relevant
- our repository's current licensing state

There is currently no top-level LICENSE file.

Determine whether one should be added for this public repository and what compatible license/notice is appropriate.

Do NOT invent a proprietary license.

Do NOT silently copy license text unless it is actually appropriate.

If adding a LICENSE or NOTICE is required/appropriate:

- use the correct text
- preserve required attribution
- document the dependency relationship accurately

If legal interpretation is genuinely uncertain, make the safest reasonable open-source-compatible choice and explain it in the final report.

This is a release hygiene task, not a request for a lengthy legal essay.

==================================================
5. VERIFY OPEN-WEIGHT MODEL CLAIM
==================================================

Verify that the README describes the model accurately.

The intended primary/default model is:

openai/gpt-oss-20b
hosted through Groq

Verify its actual published licensing/open-weight status from authoritative documentation if possible.

Use precise terminology.

Prefer:

"open-weight model"

rather than overstating "fully open-source" if that distinction matters.

The README must remain honest that:

- GPT-OSS is the intended/default model.
- The historical formal GPT-OSS evaluation did not complete because of provider quota.
- No full GPT-OSS score is claimed.
- The complete historical evaluation was DeepSeek deepseek-chat.
- We do not make an unsupported licensing claim about the DeepSeek hosted alias.

Do not hide this limitation.

==================================================
6. VERIFY GENERALIZATION / NO QUESTION LEAKAGE
==================================================

Search production model-facing code and schemas for:

- assignment example identifiers
- evaluation-specific identifiers
- question-specific routing
- known-answer mappings
- hard-coded responses
- hidden eval recipes

Especially inspect:

src/pid_agent/agent/
src/pid_agent/graph/
tool descriptions
system prompts
claim schema
planner prompt

UI example buttons are acceptable as presentation only, provided clicking them simply sends the ordinary question through the normal agent.

Tests may contain expected C01 values.

Documentation/transcripts may contain real examples.

Production reasoning logic must remain generic.

==================================================
7. VERIFY GUARDRAILS
==================================================

Run deterministic tests covering at least:

- wrong entity/value
- wrong property
- wrong semantic role
- invented property from user text
- invented connection
- user-provided correct-looking value
- warning containing identifier/value
- tool input containing unsupported value
- wrong unit
- unsafe unit reinterpretation
- reversed direction
- neighboring valve mistaken for operated valve
- false exchanger process-to-utility traversal
- truncated traversal treated as complete
- open end treated as known destination
- fuzzy suggestion treated as resolved
- ambiguous entity silently selected
- unsupported engineering/world knowledge
- prompt injection requesting graph bypass
- request for API key/system prompt
- live/current plant state assertion

Also retain positive tests for:

- exact property
- connection
- direction
- path
- line/segment
- nominal diameter
- equipment type
- instrumentation relationship
- open end
- missing property
- ambiguity
- multi-step traversal

Do not reduce coverage to make tests pass.

==================================================
8. HISTORICAL EVALUATION MUST REMAIN HISTORICAL
==================================================

The saved 15-question DeepSeek run predates structured claim grounding.

Preserve it byte-for-byte.

Do not rewrite transcripts.

Do not rewrite run.json.

Do not pretend it evaluates the current structured grounding architecture.

README should continue clearly distinguishing:

HISTORICAL FORMAL EVALUATION
from
POST-EVALUATION STRUCTURED-GROUNDING TESTS / LIVE SMOKE TEST

Run:

uv run python evals/evaluator.py

offline only to verify that the preserved historical artifacts still score identically.

Expected historical DeepSeek result should remain:

15/15 questions
mean score 1.00
41/41 required facts
0 forbidden facts

The partial GPT-OSS run must remain accurately described as partial.

==================================================
9. TIME-SPENT STATEMENT
==================================================

Do NOT automatically change the time-spent number.

The README currently says approximately 5–6 hours hands-on.

Flag this for Shaaz to confirm.

Do not fabricate a larger or smaller number from commit timestamps.

If the repository distinguishes core implementation from later optional hardening/UI/docs, suggest wording but DO NOT change it unless explicitly authorized.

Suggested wording ONLY IF TRUE:

"Approximately 5–6 hours on the core assignment, followed by an additional short pass on documentation, the optional local UI, and grounding hardening."

If that is not accurate, leave the current wording and flag it.

==================================================
10. OPTIONAL HOSTING AUDIT
==================================================

Do NOT deploy anything during this task.

Do NOT add deployment infrastructure merely because hosting is a bonus.

Assess whether the current application can be safely hosted as a public demo.

Current stack includes:

- Python
- Streamlit
- pyDEXPI
- NetworkX
- hosted LLM API

Determine the simplest sensible deployment target.

Consider:

- Streamlit Community Cloud
- Render
- Railway
- Fly.io
- other appropriate Python hosting

Do not default to Vercel unless the current Python/Streamlit architecture genuinely fits it cleanly.

For a public demo, determine the safest API-key strategy.

Preferred:
server-side secret/environment variable

NOT:
committing an API key

Do not expose GROQ_API_KEY to the browser.

Do not create a fake chatbot that doesn't use the real PidAgent.

If hosting would require material architecture changes, report:

"Local UI is release-ready; hosted demo remains optional."

Hosting is a BONUS and must not block submission.

==================================================
11. README FINAL REVIEW
==================================================

Review README from the perspective of Abdullah opening the repository for the first time.

He should understand within 60 seconds:

WHAT THIS IS

WHY IT EXISTS

HOW TO RUN IT

HOW THE GRAPH WORKS

HOW THE AGENT WORKS

HOW ANSWERS ARE GROUNDED

WHERE THE EVALUATION IS

WHAT THE LIMITATIONS ARE

Do not make README substantially longer.

Prefer removing stale/redundant material over adding more.

Check every relative link.

Check the screenshot.

Check Mermaid syntax.

Check all commands against the actual CLI.

No fake commands.

==================================================
12. FRESH-CLONE RELEASE VERIFICATION
==================================================

After any fixes, perform a clean verification from a fresh clone of the public GitHub repository.

Verify:

git clone
uv sync

Then:

uv run pytest

Expected:
all deterministic tests pass
live tests deselected unless intentionally invoked

Run:

uv run python evals/evaluator.py

Verify historical scores remain unchanged.

Run at least these deterministic commands:

uv run pid-agent tool find_entities '{"query":"P4711"}'

uv run pid-agent tool find_path '{"source_entity_id":"P4711","target_entity_id":"H1007"}'

Verify expected graph-derived behavior.

Start:

uv run pid-agent-ui

Verify:

- page loads
- no key is exposed
- graph loads
- provider/key error is clear if no key exists
- Grounding section can display:
  - grounding status
  - validated claims
  - supporting evidence
  - rejected claims where applicable
  - provenance

Stop the server afterwards.

==================================================
13. SECURITY / SECRET SCAN
==================================================

Perform a REAL full repository and Git history scan.

Do not merely scan staged diff.

Check:

- current tracked files
- full git history
- .env absence
- API keys
- Groq keys
- DeepSeek keys
- OpenRouter keys
- bearer tokens
- private URLs
- accidental credentials
- local filesystem paths
- editor files
- temporary logs

.env must remain untracked.

.env.example must contain placeholders only.

Never print a real secret in the final report.

==================================================
14. GIT RULES
==================================================

Do not:

- squash
- rebase
- amend
- rewrite history
- force push
- change existing Git identity
- fabricate timestamps
- add AI attribution
- add Co-Authored-By
- mention Claude/Copilot/ChatGPT in commit attribution

Historical prompt files may contain names if they are literal preserved instructions.

Only create commits for genuine release changes.

Possible commits if actually needed:

fix: complete submission release audit

chore: add repository licensing metadata

docs: finalize submission documentation

If a general grounding bug is found:

fix: harden structured claim validation

Do not create empty or cosmetic commit inflation.

==================================================
15. PUSH
==================================================

If and ONLY IF:

- deterministic tests pass
- historical evaluator reproduces
- stale audit is fixed
- licensing is resolved/documented
- no secret is present
- no release blocker remains
- repository is clean

then push normal commits to:

origin/main

No force push.

After pushing, verify GitHub HEAD equals local HEAD.

==================================================
16. FREEZE
==================================================

Once release verification passes:

DO NOT ADD MORE FEATURES.

Specifically do not add:

- vector DB
- BM25
- semantic retrieval
- Neo4j
- Redis
- authentication
- conversation memory
- another model
- another graph database
- another eval set
- visual P&ID highlighting
- deployment infrastructure
- additional abstraction layers

The assignment is finished.

==================================================
17. FINAL REPORT
==================================================

Return exactly:

# RELEASE READINESS COMPLETE

## 1. Final verdict
READY TO SEND
or
NOT READY TO SEND

If not ready, list only actual blockers.

## 2. Assignment mapping
Table:

Abdullah requirement | Status | Evidence | Limitation

Cover every explicit requirement.

## 3. Structured grounding verification
- architecture verified
- live smoke results
- number grounded
- number limited
- regenerations
- fallbacks
- any unsupported prose found
- any fixes made

## 4. Guardrail verification
List adversarial categories tested and results.

## 5. Tests
- deterministic test count
- pass/fail/deselected
- historical evaluator result

## 6. Historical evaluation integrity
Confirm artifacts unchanged and explain that they predate structured grounding.

## 7. Open-weight model
State:
- default provider/model
- verified licensing terminology
- GPT-OSS historical evaluation status
- DeepSeek historical evaluation status

## 8. Licensing
State exactly what was found and what was changed.

## 9. Security
- secret scan
- .env status
- credential status

## 10. Fresh clone
List commands actually run and results.

## 11. Documentation
List stale statements fixed and links checked.

## 12. Hosting
Recommend the simplest target but confirm whether hosting remains optional.

DO NOT deploy.

## 13. Time spent
State:
"Requires Shaaz confirmation"
unless Shaaz explicitly supplied a final truthful number.

## 14. Git
List new commits.
State final HEAD.
Confirm normal push only.
Confirm origin/main == local HEAD.

## 15. Remaining limitations
Only genuine limitations.

## 16. Submission package
Provide:

Repository:
https://github.com/shaaz1000/pid-graph-agent

Run:
uv sync
uv run pid-agent "What is P4711 connected to, and through which pipes?"

UI:
uv run pid-agent-ui

Then state exactly:

READY TO SEND TO ABDULLAH

if and only if there are no blockers.
