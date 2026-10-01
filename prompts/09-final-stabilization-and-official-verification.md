We have reviewed the frozen DeepSeek diagnostic run at commit:

308dc59

Results:

- 6 correct
- 1 partially correct
- 1 correct draft withheld by grounding
- 0 turn-limit hits
- 0 duplicate calls
- 0 malformed calls
- instrumentation composition now works
- missing-data handling works
- ambiguity handling works
- property attribution mostly works

We are approving ONE final stabilization patch before the official Groq
verification.

This is NOT another tuning round.

Do not run DeepSeek again after implementing these changes.

Do not start M3.

Save this instruction as the next sequential prompt-history file before
implementation.

============================================================
1. APPROVED FIX A — STRUCTURED CHAMBER-BOUNDARY EVIDENCE
============================================================

Q1 exposed a genuine general grounding contradiction.

Current behavior:

1. deterministic traversal encounters a chamber boundary
2. graph-derived identifiers are placed inside a warning
3. the model is shown the warning
4. the model mentions those identifiers in its answer
5. grounding ignores warning contents because warnings may echo user input
6. grounding rejects the otherwise correct answer

Observed unsupported identifiers included:

Chamber-4
PipingNetworkSegment-23/connections/1

Do NOT solve this by allowing arbitrary warning text to count as evidence.

Warnings may contain echoed user input and must remain non-authoritative for
grounding.

Instead:

represent graph-derived chamber-boundary facts as STRUCTURED TOOL EVIDENCE.

The structured representation should contain only facts deterministically
derived from the graph.

Use the existing tool-result/evidence conventions where possible.

Conceptually it may contain fields such as:

boundary_type
entity/equipment involved
chamber id
connection id
reason traversal was blocked/skipped
direction
provenance

Do not blindly implement those exact field names if the existing data model
has a better representation.

The important invariant is:

GRAPH-DERIVED CHAMBER BOUNDARY FACTS
must be represented as structured evidence

while:

HUMAN-READABLE WARNINGS
remain non-authoritative for grounding.

Do not duplicate user-controlled text into authoritative evidence.

============================================================
2. GROUNDING FOR STRUCTURED BOUNDARY FACTS
============================================================

Update grounding so claims about graph-derived chamber-boundary identifiers
can be supported by the new structured evidence.

Do NOT globally loosen grounding.

Do NOT make all warnings evidence.

Do NOT accept arbitrary identifiers merely because they appear somewhere in
tool output.

Maintain contextual/role-aware grounding.

Examples:

a chamber identifier should be grounded as a chamber

a connection identifier should be grounded as a connection

Do not allow an identifier to support an unrelated semantic role.

============================================================
3. APPROVED FIX B — TRUNCATED TRAVERSAL FRONTIER SEMANTICS
============================================================

Q2 exposed another general semantic problem.

The model explicitly requested:

max_depth=4

The deterministic result correctly reported:

truncated_by_max_depth: true

and warned that further entities were omitted.

However, the answer treated some frontier entities as though branches ended
there.

We do NOT want:

- a P4712-specific fix
- a discharge-specific fix
- automatic unlimited traversal
- hidden business semantics
- a special pump tool

Instead make traversal frontier semantics explicit.

When traversal stops at max_depth while graph continuation exists, the
structured result should distinguish:

TRUE TERMINAL
nothing further is represented in that traversal direction

from:

TRUNCATED FRONTIER
this entity is at the requested traversal boundary but graph continuation
exists beyond the returned result

Use the existing traversal result model where possible.

Conceptually this could be represented with something like:

terminal: true/false

and/or:

frontier: true
continues_beyond_result: true

Do not use those exact fields if a cleaner representation already exists.

The important invariant is:

AN ENTITY MUST NOT APPEAR TERMINAL MERELY BECAUSE max_depth CUT OFF THE
TRAVERSAL.

============================================================
4. COMPACTION MUST PRESERVE THIS
============================================================

Ensure the compact model-facing traversal representation preserves:

- truncated_by_max_depth
- true terminal status
- truncated frontier status
- continuation beyond returned result
- relevant endpoint information
- through_equipment
- chamber-boundary structured evidence

The model should not need to infer truncation from a prose warning.

The structured result should make it obvious.

============================================================
5. ANSWER SEMANTICS
============================================================

Do not add question-specific prompt rules.

A generic instruction may say, if not already adequately expressed:

When traversal is truncated, do not describe frontier entities as final
destinations unless the graph evidence marks them terminal. State that the
returned traversal does not establish what lies beyond the frontier.

Keep this generic.

Do not mention:

P4712
T4750
C5
C7
H1008

in the production system prompt or tool descriptions.

============================================================
6. DO NOT FIX SLASH-JOINED NOZZLE NAMES NOW
============================================================

Q5 exposed:

N1/N2
N3/N4

being rejected as combined identifiers.

The regeneration recovered and produced the correct final answer.

Do NOT modify grounding for this in this patch.

Record it as a known minor limitation.

We do not need every cosmetic identifier construction to pass without
regeneration.

============================================================
7. DO NOT CHANGE INSTRUMENTATION
============================================================

Q3 and Q4 demonstrated that the instrumentation changes are now working.

Do NOT modify:

instrumentation relationship semantics
alias handling
instrumentation traversal
failAction handling

without a regression caused by this patch.

============================================================
8. DO NOT CHANGE PROPERTY LOGIC
============================================================

Q5 demonstrated:

- design-pressure lookup works
- per-chamber attribution works
- typographic minus normalization works
- incorrect "DN 800" was correctly rejected

Do NOT loosen property grounding.

The DN 800 rejection is desirable behavior.

============================================================
9. TESTS FOR FIX A
============================================================

Add deterministic regression coverage proving:

1. graph-derived chamber-boundary facts appear as structured evidence

2. chamber identifiers in that structured evidence can ground chamber claims

3. connection identifiers in that structured evidence can ground connection
   claims

4. warnings themselves still do NOT become grounding evidence

5. user-controlled text appearing only in a warning cannot ground a claim

6. the previously observed Q1-style correct draft is accepted using structured
   evidence

Use generic fixtures/behavior where possible.

Do not write a test whose only purpose is matching the exact natural-language
Q1 string.

============================================================
10. TESTS FOR FIX B
============================================================

Add deterministic regression coverage proving:

1. true terminal entities remain terminal

2. max-depth frontier entities with outgoing graph continuation are NOT marked
   terminal

3. truncated frontier status survives compaction

4. truncated_by_max_depth survives compaction

5. model-facing results distinguish terminal from truncated frontier

6. a branch with continuation beyond max_depth is not represented as having
   ended at the frontier

Use multiple entities/fixtures where practical.

Do not special-case P4712.

============================================================
11. NO LIVE DEEPSEEK RERUN
============================================================

After implementing these fixes:

DO NOT run the eight DeepSeek questions again.

We already obtained the diagnostic information we needed.

A second run would start turning the diagnostic set into a tuning benchmark.

The next real-model measurement is the frozen Groq verification.

============================================================
12. FULL REGRESSION
============================================================

Current baseline:

363 passed
0 failed
4 live deselected

After implementation:

run the full deterministic suite.

Report:

new total
passed
failed
live deselected

Do not optimize for test count.

============================================================
13. COMMIT
============================================================

If all deterministic tests pass:

perform secret scan

inspect diff

inspect staged diff

ensure .env is not staged

ensure no API keys are staged

then create ONE final stabilization commit.

Suggested subject:

fix: preserve traversal boundary evidence

Use a different concise subject only if it more accurately describes the
actual patch.

Do not amend existing commits.

Do not rewrite history.

Do not push.

============================================================
14. ARCHITECTURE FREEZE AFTER THIS COMMIT
============================================================

After this commit:

THE AGENT ARCHITECTURE IS FROZEN.

Do not make another agent change before the official Groq run.

This includes:

- prompts
- tools
- graph semantics
- traversal
- grounding
- compaction
- budgets
- state reuse
- provider behavior

unless an infrastructure issue makes the run impossible.

============================================================
15. GROQ VERIFICATION
============================================================

Do not probe Groq repeatedly.

When sufficient quota is expected to have returned, make one minimal capacity
check.

If insufficient:

STOP and report infrastructure block.

If sufficient:

record:

git rev-parse HEAD

git status --short

Then explicitly use:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

Run the existing frozen five-question official M2.2 set exactly once.

Do not change those questions.

Do not retry answers.

Do not modify implementation between questions.

============================================================
16. OFFICIAL FIVE-QUESTION RESULT
============================================================

For every question record:

- exact question
- provider
- model
- tool sequence
- tool calls
- model calls
- tokens
- latency
- final answer
- grounding result
- unsupported claims
- fallback used
- outcome

Outcome:

correct
partially_correct
incorrect
abstained
infrastructure_failure

============================================================
17. IMPORTANT EVALUATION RULE
============================================================

The Groq run is measurement, not development.

If question 1 fails:

continue unchanged.

If question 2 fails:

continue unchanged.

Continue through all five.

Do not patch anything until all five results have been recorded.

============================================================
18. FREEZE DECISION
============================================================

After the five questions recommend:

READY_FOR_M3

or:

BLOCKING_GENERALIZATION_ISSUE

READY_FOR_M3 does not require 5/5.

A model mistake or documented limitation is not automatically an architecture
failure.

Only recommend another architecture change if the frozen Groq run exposes a
repeatable, general defect likely to materially affect unseen questions.

============================================================
19. NO M3 YET
============================================================

Do NOT create the final evaluation set.

Do NOT run formal evaluation.

Do NOT calculate final evaluation score.

Do NOT start M4.

Wait for my review.

============================================================
20. FINAL REPORT
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
  Commit: <hash>
  Tests: <result>

✓/! M2.2b — Official Groq verification
  Commit tested: <hash>
  Provider: groq
  Model: openai/gpt-oss-20b
  Result: <result or infrastructure blocked>

→ M3 — Formal evaluation
  Recommendation: READY_FOR_M3 / BLOCKING_GENERALIZATION_ISSUE

Then report:

A. FIX A IMPLEMENTATION

B. FIX B IMPLEMENTATION

C. REGRESSION TESTS

D. FINAL STABILIZATION COMMIT

E. OFFICIAL GROQ RESULTS

Question | Outcome | Model calls | Tool calls | Tokens | Grounding

F. Q5-STYLE REACHABILITY STATUS

G. Q12-STYLE INSTRUMENTATION STATUS

H. Q13-STYLE PROPERTY/GROUNDING STATUS

I. REMAINING LIMITATIONS

J. TOKEN/CALL EFFICIENCY

K. SECRET SCAN

L. GIT STATUS

M. FREEZE RECOMMENDATION

Then STOP.

Do not start M3.
