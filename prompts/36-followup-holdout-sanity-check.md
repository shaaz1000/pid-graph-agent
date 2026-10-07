We have completed Sachin's formal follow-up evaluation and the post-evaluation
security hardening.

Before emailing him, I want ONE final holdout sanity check on the CURRENT
hardened main branch.

This is NOT another tuning cycle.

Do not modify architecture, prompts, tools, resolver, evaluator, or graph logic
based on the results.

The purpose is simply to answer:

1. Can the hardened current system answer fresh complex P&ID questions?
2. Does it remain stable when those fresh complex questions are rephrased?
3. Did the post-evaluation security hardening preserve normal functionality?

==================================================
PHASE 1 — VERIFY SACHIN REQUIREMENT COVERAGE
==================================================

First produce a checklist against the follow-up PDF.

For each requirement state:

PASS / PARTIAL / NOT DONE

Specifically verify:

- all C1-C15 were run
- at least 10 additional complex questions were added
- all provided rephrasing groups were run
- at least 5 additional rephrasing groups with 4+ phrasings were added
- at least 2 added groups are based on complex questions
- each phrasing was run independently 3 times
- repeat consistency was measured
- cross-phrasing consistency was measured
- automated evaluator exists
- inconsistencies are classified
- visible traces are preserved
- short follow-up note exists
- no fixed phrase-to-tool mappings
- semantic regex is no longer the primary grounding mechanism
- real commit history is preserved

Do not change anything during this checklist.

==================================================
PHASE 2 — CREATE A FRESH HOLDOUT SET
==================================================

Create a NEW small holdout set that has never appeared in:

- prompts
- current eval question files
- README examples
- Sachin's provided PDF
- previous smoke tests

Do not reuse the same wording.

Target:

8 fresh complex questions.

They must require at least 2 graph operations or one genuinely multi-hop graph
analysis.

Cover 8 different reasoning patterns where the graph supports them, such as:

1. isolation boundary + unresolved gap
2. path comparison
3. instrumentation chain + piping context
4. branch-aware line tracing
5. hypothetical reachability after removing/closing a component
6. inventory filtered by multiple attributes
7. upstream/downstream reach with recycle or branch structure
8. relief-path or open-end reasoning

Do not force these categories if C01 cannot support them.

Every question must be objectively scoreable from deterministic graph
operations.

For each question, derive BEFORE inference:

- required facts
- required unknowns
- acceptable partial answer
- forbidden unsupported conclusions

Save this as a separate:

evals/followup/holdout/

Do not modify the official follow-up scores.

==================================================
PHASE 3 — FRESH COMPLEX REPHRASING GROUPS
==================================================

Choose 3 of the new complex questions.

For each, create 4 genuinely different phrasings.

Each set should vary reference style:

- exact tag
- equipment/type description
- property/context description
- terse operator-style wording

Examples of variation style only:

"Which..."
"What remains reachable if..."
"Suppose..."
"Trace..."
"From the ... side..."
"The item with ..."

Do NOT copy phrases from Sachin's PDF.

Do NOT add these phrases to prompts or resolver aliases.

We want 3 new groups × 4 phrasings = 12 questions.

==================================================
PHASE 4 — FREEZE BEFORE RUNNING
==================================================

Before any model calls:

- save the holdout questions
- save deterministic gold
- record current HEAD
- ensure working tree is clean
- run deterministic tests
- record test count

Do not alter the holdout after seeing results.

==================================================
PHASE 5 — RUN WITH EXISTING NVIDIA NEMOTRON
==================================================

Use:

nvidia/nemotron-3-super-120b-a12b

through the existing NVIDIA endpoint.

No paid provider.

Do not switch models.

Run:

A. 8 complex holdout questions
   - one run each

B. 3 rephrasing groups
   - 4 phrasings each
   - 2 independent repeats each

This is 24 rephrasing runs.

Total new inference runs:
32

Do NOT run 3 repeats because the formal 3-repeat requirement has already been
satisfied in the official evaluation.

This is only a final sanity/holdout check.

==================================================
PHASE 6 — SCORE CORRECTNESS
==================================================

For the 8 complex questions report:

- fully correct
- partial
- incorrect
- withheld
- required-fact recall
- required-unknown recall
- contradictions
- unsupported facts
- planner/tool-choice failures
- incomplete traversal
- entity-resolution failures
- grounding failures

Also report mean score.

==================================================
PHASE 7 — SCORE REPHRASING STABILITY
==================================================

For each of the 3 groups report:

1. within-phrasing repeat consistency
2. cross-phrasing required-fact consistency
3. semantic correctness
4. entity-resolution consistency
5. contradiction count
6. tool-choice variation
7. unknown/not-in-drawing consistency

Important:

An extra supported fact should NOT automatically count as inconsistency.

Count inconsistency when:
- a required fact is missing in one answer
- facts contradict
- entity resolution changes incorrectly
- an unknown becomes an invented fact
- path/boundary/property result changes materially

==================================================
PHASE 8 — SECURITY SANITY CHECK
==================================================

Because main now includes post-evaluation status hardening, audit every holdout
answer for:

- model-controlled tool input appearing in rendered output
- status text using non-canonical spelling
- model-authored factual prose appearing
- uncited/unsupported structured facts

Expected:
0 in all categories.

Also deliberately include ONE adversarial internal test where a model-controlled
lookup query contains sentence-like text.

Do not make that a user-facing evaluation question.

Verify that the model-controlled sentence cannot appear in the rendered answer.

==================================================
PHASE 9 — NO TUNING
==================================================

After the holdout starts:

Do NOT:
- modify code
- modify prompts
- modify gold
- rerun bad answers
- change questions
- add phrase aliases
- add question-specific routing
- increase step limits
- repair individual failures

This is measurement only.

==================================================
PHASE 10 — FINAL REPORT
==================================================

Return:

A. Sachin requirement checklist
B. hardened current HEAD
C. deterministic test count
D. 8-question holdout results
E. 3-group rephrasing results
F. repeat consistency
G. paraphrase consistency
H. semantic correctness
I. unsupported fact count
J. contradiction count
K. security/provenance audit
L. major failure causes
M. whether post-evaluation hardening broke anything
N. recommendation:
   READY TO EMAIL SACHIN
   or
   NOT READY

Do not commit the holdout artifacts yet.
Do not email Sachin.
Do not change implementation.

STOP after reporting.
