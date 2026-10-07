Approve the final closure pass.

Do NOT modify or rerun the official 150-run evaluation.
Do NOT change the existing holdout-2 questions, gold, or recorded results.
Do NOT run another benchmark after these fixes.

The goal is to close the two remaining security/semantic issues and bring docs/artifacts in sync.

==================================================
1. FIX EMPTY / NOTHING-REACHED FACT SEMANTICS
==================================================

A traversal-derived absence fact must record enough context to be meaningful.

For any "nothing reached" / empty reachability fact, carry at least:

- start entity
- direction
- blocked entities
- entity-type filter, if any
- depth/search bound
- whether the traversal completed without truncation

Rules:

- If the traversal completed and found no matching entity under the stated filter,
  it may support a definitive absence fact.
- If the traversal was depth-limited/truncated, it must NOT support a definitive
  "nothing reached" conclusion.
- If no entity-type filter was used, the result must not be interpreted as
  "no equipment reached" merely because no equipment row was cited.
- Render the absence with fixed application wording.

Add deterministic tests for:
- empty completed traversal with equipment filter
- empty completed traversal without filter
- truncated empty traversal
- blocked-item traversal
- different direction
- same start but different filters producing distinct facts

No prose validator.

==================================================
2. REMOVE TRUST FROM MODEL-ASSIGNED KIND
==================================================

The current enforcement relies too much on the model's requested-output kind.

That label may remain useful for planning, but it must NOT be the trust boundary
for what a cited operation can prove or which composite rows complete an answer.

Change the final validation/completion logic so it derives capability from:

- the cited operation/tool
- the operation's result schema/predicates
- route semantics
- deterministic output structure

The model's kind may suggest a capability, but it cannot weaken or strengthen
what the evidence is allowed to prove.

Examples:

A. If `trace_instrumentation` is cited, the application can deterministically
   identify the loop's measurement point, signal chain, final element, fail action
   and line context from its rows, regardless of whether the model labelled the
   requested output "items", "property" or "signal_chain".

B. If `isolation_boundary` is cited, the application can deterministically
   identify boundary valves, unisolated connections and relief-related rows,
   regardless of the model's label.

C. A topological route can NEVER satisfy a process-flow/reachability conclusion,
   even if the model labels the output incorrectly.

D. A drawn-flow route/reachability result may support process reachability if its
   semantics and direction actually match.

Do not create question-specific routing.
Do not use tags or supplied phrases.

Add tests proving:
- wrong model kind does not bypass flow-safety rules
- wrong model kind does not suppress composite completion
- model kind cannot convert topological evidence into flow evidence
- operation schema determines allowable completion
- unrelated rows are still excluded

==================================================
3. PRESERVE PLANNING BEHAVIOUR
==================================================

Do not remove the capability-planning layer.

The model may still choose kinds and capabilities for planning.

Only final trust/completion moves to deterministic operation semantics.

==================================================
4. COMMIT HOLDOUT-2 ARTIFACTS UNCHANGED
==================================================

Commit the existing holdout-2 run artifacts exactly as recorded.

Clearly label them:

POST-EVALUATION ARCHITECTURE HOLDOUT 2

Record:
- evaluated SHA: 1abcc01
- clean tree
- 8 complex questions
- 4 rephrasing groups × 4 phrasings × 2 repeats
- 40 runs
- results exactly as already reported
- no post-result tuning before the recorded run

Do not rescore by changing gold.

==================================================
5. UPDATE DOCUMENTATION
==================================================

Update README and follow-up docs to describe:

- capability declarations / constrained planning
- deterministic composite completion based on operation semantics
- explicit topological vs drawn-flow route semantics
- citable completed empty traversal facts
- holdout-2 results
- that the earlier backwards-relief-path issue was exposed by the first holdout
  and is now blocked from satisfying process-flow questions
- planning/kind assignment remains variable, but the trust boundary no longer
  depends on the model-assigned kind

Keep the official 150-run metrics unchanged and clearly historical.

Do not overclaim consistency improvement.

Use wording such as:

"The post-evaluation architecture hardening prevents direction-agnostic
connectivity from satisfying process-flow outputs and completes composite
analysis results deterministically from operation semantics. A second frozen
holdout found 0 process-route semantic errors, 0 contradictions and 0 unsupported
facts, while planner/kind-selection variance remained."

==================================================
6. TESTS AND SECURITY CHECK
==================================================

Run:
- full deterministic tests
- secret scan
- docs link check if available

Add adversarial tests for:
- model assigns wrong kind to a flow question
- model assigns generic "items" to instrumentation
- topological path through relief/check device
- truncated empty traversal
- unfiltered traversal cited as equipment absence

No live NVIDIA calls.

==================================================
7. COMMITS
==================================================

Use separate logical commits:

fix: make absence facts filter- and truncation-aware

fix: derive answer completion and flow safety from operation semantics

eval: record second architecture holdout

docs: describe post-evaluation architecture hardening

Do not squash.

==================================================
8. FINAL REPORT
==================================================

Return:
- commit hashes
- final test count
- files changed
- confirmation official evaluation artifacts unchanged
- confirmation holdout-2 artifacts unchanged
- confirmation no live model run occurred after the fixes
- exact docs updated
- working tree status
- origin/main == local HEAD
- final recommendation READY / NOT READY

STOP.
Do not email Sachin.
