We are doing ONE final post-evaluation architecture hardening pass.

Do NOT modify or rerun the official 150-run evaluation.
Commit 87953f4 and all official artifacts remain historical and unchanged.

The goal is to fix three GENERAL failure modes discovered by the evaluation:

1. planner/tool-choice variance across paraphrases;
2. incomplete citation of facts already returned by a composite graph analysis;
3. confusion between topological connectivity and directional/process reachability.

No question-specific logic is allowed.

==================================================
1. CAPABILITY-CONSTRAINED PLANNING
==================================================

Current flow:

question
-> decompose_request
-> model freely chooses graph tools
-> submit_answer

Add a typed capability-planning layer between decomposition and execution.

Each generic graph capability should declare the classes of outputs it can
produce.

Examples conceptually:

isolation_boundary:
- boundary valves
- unisolated connections
- relief connections

trace_instrumentation:
- measurement point
- signal chain
- final element
- fail action
- piping context

trace_line:
- branches
- run endpoints
- size changes
- line junctions

find_path:
- routes/reachability

traverse:
- reachable entities

Do not use literal phrases from any evaluation question.

Do not create:
"isolate" -> isolation_boundary
"loop" -> trace_instrumentation

Instead use the structured requested-output representation already produced by
decompose_request.

The planner may choose among capabilities compatible with each requested
output, but incompatible generic operations should not be sufficient to mark
that output complete.

The purpose is to reduce arbitrary tool selection without removing LLM intent
interpretation.

==================================================
2. COMPLETE COMPOSITE RESULTS
==================================================

A repeated formal-evaluation failure was:

the correct composite operation ran,
but the model cited only some of its relevant rows.

Example class:
isolation_boundary returns valves + relief/gap information,
but the answer selects only the valves.

Fix this generically.

Allow a requested output to be covered by a coherent analysis result/bundle.

When a composite graph operation deterministically defines the complete answer
for that requested output, application code should select/render the relevant
rows belonging to that output rather than asking the model to individually
remember every row.

Do not blindly print every tool row.

The mapping must come from:
- operation output schema
- requested output kind
- deterministic row predicates

not question wording.

Add tests showing:
- required boundary facts are not silently omitted
- instrumentation-chain components remain complete
- irrelevant rows are not added

==================================================
3. EXPLICIT ROUTE SEMANTICS
==================================================

Separate:

A. topological connectivity
B. drawn-flow/process-direction reachability

A direction-agnostic graph path must NOT support a process-reachability claim.

Represent this explicitly in the path/reachability result.

Preferred conceptual API:

route_semantics:
- topological
- drawn_flow

or an equivalent strongly typed design.

Rules:

- "Are A and B connected?" may use topological connectivity.
- process reachability / feeds / flows / downstream consequences require
  drawn-flow semantics.
- a topological route remains valid evidence only for connectivity.

The known example:

T4750 -> SV 104.01 -> piping -> P4712

must remain discoverable as topological connectivity if direction is ignored,
but must NOT support a claim that T4750 can feed/reach P4712 in drawn process
direction.

Do not special-case:
- T4750
- SV104.01
- P4712
- relief valves by tag

The behaviour must emerge from generic edge direction / device semantics.

==================================================
4. COVERAGE VALIDATION
==================================================

Strengthen requested-output coverage so that:

"something cited for q1"

is not automatically equal to:

"q1 was fully answered."

For output kinds backed by a deterministic composite analysis, validate required
result categories structurally.

Example conceptually:

boundary output:
- boundary devices
- gaps/unisolated connections
- relevant relief condition

instrument-loop output:
- source/measurement
- intermediate signal chain
- final element
- requested fail action/context when present

Do this using result schemas/predicates, not evaluation gold.

==================================================
5. DO NOT CHANGE THE FORMAL EVALUATION
==================================================

Do not:
- alter official questions
- alter official gold
- rescore 87953f4 as if new code produced it
- replace any historical result
- rerun poor historical answers

The report must continue to say the formal follow-up scored what it actually
scored.

==================================================
6. TESTS
==================================================

Add deterministic tests for:

- same requested-output structure expressed with different wording leads to the
  same compatible capability set
- incompatible tool result cannot fully cover a requested output
- complete isolation result renders all relevant categories
- complete loop result does not omit final element
- topological route cannot cover process-direction reachability
- directional route can
- backwards traversal through a relief/check device does not become
  process-direction evidence
- no question ids, tags or supplied phrases appear in routing logic

Run full deterministic tests.

==================================================
7. FRESH HOLDOUT ONLY
==================================================

After implementation is frozen, create a NEW holdout not present anywhere else.

Before inference:
- freeze questions
- freeze graph-derived gold
- commit implementation
- record SHA
- clean tree

Use NVIDIA Nemotron, no paid provider.

Run:

8 fresh complex questions

plus

4 new paraphrasing groups
× 4 phrasings
× 2 repeats

= 32 paraphrase runs

Total 40 scheduled runs.

Include at least:
- an isolation completeness case
- directional-vs-topological route case
- instrumentation-chain case
- blocked-item reachability
- branching/line case

Do not reuse Sachin's wording.

==================================================
8. SUCCESS CRITERIA
==================================================

This is not a perfection benchmark.

I want to know whether the architecture improved the observed failure classes.

Report:

- complex correctness
- required-fact recall
- repeat consistency
- paraphrase consistency
- tool/capability stability
- retrieved-but-omitted fact count
- process-route semantic errors
- contradictions
- unsupported facts
- provider failures

Compare only descriptively against the earlier holdout.

Do not claim direct score improvement if question sets differ.

==================================================
9. STOP
==================================================

Return:

- architecture changes
- why they are generic
- files changed
- tests
- commit SHA
- fresh holdout definition
- fresh holdout results
- remaining failures
- whether the three target failure modes improved
- recommendation READY / NOT READY

Do not email Sachin.
Do not touch the official evaluation artifacts.

STOP.
