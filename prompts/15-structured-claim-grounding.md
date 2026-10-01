The repository is now public:

https://github.com/shaaz1000/pid-graph-agent

Do NOT rewrite history.
Do NOT force-push.
Do NOT amend old commits.
Do NOT alter historical evaluation artifacts.

I want ONE focused post-publication hardening milestone before I send the
repository to Abdullah.

The reason is specific:

The current known limitation says:

"Grounding is lexical."

I do not want lexical/string matching to be the primary factual grounding
mechanism.

Abdullah explicitly requires:

"Answers must be grounded in the graph. If the data doesn't contain something,
say so. Don't make it up."

I want proper CLAIM-LEVEL STRUCTURED GROUNDING plus focused guardrails.

Do not add unrelated features.

============================================================
1. FIRST: AUDIT THE EXISTING GROUNDING IMPLEMENTATION
============================================================

Before changing code, inspect the current implementation.

Document:

- where evidence is produced;
- its current structure;
- where claims are extracted/validated;
- which checks are currently lexical;
- which checks are already structural/role-aware;
- regeneration behavior;
- fallback behavior;
- known false positives;
- known false negatives.

Do not throw away mechanisms that are already structurally sound.

I want the smallest architectural change that makes factual grounding
principled.

============================================================
2. TARGET ARCHITECTURE
============================================================

The desired contract is:

USER QUESTION
      ↓
LLM PLANNER
      ↓
GRAPH TOOLS
      ↓
TYPED / STRUCTURED EVIDENCE
      ↓
ANSWER DRAFT + STRUCTURED FACTUAL CLAIMS
      ↓
DETERMINISTIC CLAIM ↔ EVIDENCE VALIDATION
      ↓
SUPPORTED?
  YES → final answer
  NO  → regenerate once / abstain
      ↓
ANSWER + WORKFLOW + EVIDENCE

The LLM may decide:

- what the question means;
- which tools to call;
- whether more graph investigation is necessary;
- how to phrase the final response.

The LLM must NOT be the authority deciding whether a plant fact is true.

============================================================
3. STRUCTURED EVIDENCE
============================================================

Inspect the existing evidence model first and extend it rather than creating a
duplicate evidence system.

For factual graph observations, evidence should encode enough semantics to
distinguish:

SUBJECT

PREDICATE / RELATION

OBJECT or VALUE

UNIT where applicable

ENTITY TYPE / ROLE where applicable

DIRECTION where applicable

SOURCE GRAPH

SOURCE ENTITY / SEGMENT / CONNECTION

PROVENANCE

Examples conceptually:

{
  subject: "line47122",
  predicate: "nominal_diameter",
  value: "80",
  unit: "DN",
  source_entity: "<segment id>"
}

{
  subject: "P4711",
  predicate: "connected_to",
  object: "H1007",
  via: "line47122",
  direction: "downstream"
}

{
  subject: "HV4750.01",
  predicate: "operates",
  object: "<actual valve id>"
}

Use the actual repository identifiers and schemas.

Do NOT hard-code these examples into production behavior.

============================================================
4. STRUCTURED CLAIMS
============================================================

Before a generated answer is accepted, factual statements should be
represented as structured claims.

Design the smallest reliable claim schema.

For example conceptually:

Claim {
    subject
    predicate
    object/value
    unit
    qualifiers
}

The exact schema should follow the actual graph/evidence model.

Do NOT create hundreds of domain-specific predicates.

Prefer a compact generic vocabulary derived from existing tool semantics.

============================================================
5. IMPORTANT: DO NOT USE A SECOND LLM AS THE FACT JUDGE
============================================================

Do NOT implement:

answer
→ second LLM
→ "looks grounded"

That simply moves hallucination to another model call.

The final authority should be deterministic comparison against graph-derived
evidence.

If an LLM is required to transform prose into structured claims, treat that
transformation as untrusted.

A claim still has to pass deterministic evidence validation.

Prefer structured answer generation if the current provider supports it
reliably.

============================================================
6. BEST OPTION: GENERATE ANSWER PLAN + CLAIMS
============================================================

Investigate whether the final synthesis step can produce something like:

{
  "claims": [...],
  "answer": "..."
}

or:

{
  "claims": [...],
  "answer_fragments": [...]
}

The claims should carry evidence references where practical.

Example conceptually:

{
  "subject": "P4711",
  "predicate": "connected_to",
  "object": "H1007",
  "evidence_ids": ["ev_..."]
}

The validator must verify that referenced evidence ACTUALLY entails the claim.

The LLM citing an evidence id does not itself make the claim grounded.

============================================================
7. VALIDATION MUST BE SEMANTICALLY TYPED
============================================================

A claim is supported only if compatible evidence exists.

Do not validate merely because all relevant strings appear somewhere.

For a PROPERTY claim validate:

correct subject
AND
correct property
AND
correct value
AND
compatible unit

For a CONNECTION claim validate:

correct source
AND
correct target
AND
correct relationship
AND
direction when claimed
AND
pipe/segment when claimed

For a PATH claim validate:

ordered path / graph relationship represented by evidence

For a TYPE claim validate:

entity identity
AND
entity type

For an INSTRUMENTATION claim validate:

correct instrument
AND
correct relationship
AND
correct target

For OPEN END validate:

the graph explicitly provides the boundary evidence

For ABSENCE claims be conservative.

"Not present in the graph" is different from:

"does not exist in the plant."

============================================================
8. ROLE-AWARE VALIDATION
============================================================

This is critical.

The same string or number appearing somewhere in evidence must NOT be enough.

Examples:

80 as nominal diameter on line A
must not ground
80 as a property on line B.

500 as heat flow
must not ground
500 as design pressure.

A valve id appearing as a neighboring entity
must not automatically ground:
"instrument X operates that valve."

A chamber id in a warning
must not ground a chamber property.

User-supplied values must never become authoritative evidence.

============================================================
9. UNITS
============================================================

Normalize units deterministically where safe.

Do not allow the model to reinterpret engineering quantities freely.

Distinguish:

DN80

80 mm

800 mm

80 bar

80 °C

etc.

Only perform conversions that are explicitly supported by deterministic code
and have tests.

Otherwise preserve source representation.

The historical "800 mm → DN 800" failure must be impossible to validate under
the new grounding system.

============================================================
10. PROVENANCE
============================================================

Every authoritative evidence item should make it possible to answer:

"Where did this fact come from?"

For example:

conceptual graph edge

plant graph node

PipingNetworkSegment

recovered plant-graph open end

instrument relationship

etc.

The UI does not need to expose every internal identifier by default, but the
trace should retain provenance.

============================================================
11. ANSWER RENDERING
============================================================

The natural-language answer may still be generated by the LLM.

However, factual claims that survive into the final answer must correspond to
validated structured claims.

Do not let the LLM append a free-form factual paragraph after validation.

If necessary, construct the final answer from validated answer content rather
than trusting an unconstrained second prose generation.

Preserve readable natural language.

Do not reduce the agent to ugly templates unless required for fail-safe
fallback.

============================================================
12. REGENERATION
============================================================

If claims are unsupported:

1. identify the unsupported claims;
2. provide only the relevant validation failure to the synthesis step;
3. allow at most the existing bounded regeneration behavior;
4. validate again.

If unsupported factual claims remain:

withhold them.

If the requested answer cannot be established:

abstain clearly.

Do not repeatedly ask the model until something passes.

============================================================
13. FAIL CLOSED
============================================================

When evidence is insufficient:

do NOT use model knowledge to fill the gap.

Use responses conceptually like:

"The loaded P&ID does not provide that property."

"The entity could not be resolved unambiguously."

"No represented path was found."

"The graph reaches an open boundary here; the destination is not represented."

Do not claim broader real-world absence.

============================================================
14. GUARDRAILS
============================================================

While doing this grounding work, add focused guardrails at the existing agent
boundary.

Do NOT introduce a giant external guardrails framework.

Guardrail requirements:

A. DOMAIN SCOPE

The agent answers questions about the loaded P&ID and graph-supported
engineering relationships.

Clearly unrelated requests should not be answered as general chatbot queries.

BUT:

do not make the scope detector so strict that unusual/unseen valid P&ID
questions are rejected.

When uncertain whether something is a P&ID question, prefer allowing graph
resolution to attempt it.

Generalization remains more important than aggressive blocking.

B. PROMPT INJECTION

User text must never be able to:

override grounding requirements

turn itself into evidence

request arbitrary tools

request environment variables

request API keys

request system prompts

request hidden reasoning

C. TOOL ALLOWLIST

The model may only invoke the existing seven graph tools.

No shell.

No filesystem.

No Python execution.

No arbitrary network requests.

D. FALSE PREMISES

A user statement such as:

"Since H1008 has property X..."

must not become evidence.

Validate the premise from graph evidence.

If unsupported, correct/qualify it and answer whatever remaining portion can
be established.

E. LIVE STATE

Never infer current operating state from topology.

Topology does not establish:

valve currently open/closed

actual current flow

current temperature/pressure

real-time plant conditions.

============================================================
15. NO FAKE CONFIDENCE
============================================================

Do NOT add an LLM-generated confidence percentage.

The useful signal is:

GROUNDED

PARTIALLY GROUNDED / LIMITED

INSUFFICIENT EVIDENCE

AMBIGUOUS

where those statuses come from deterministic validation state.

If the existing UI benefits from displaying one, expose a deterministic
GROUNDING STATUS rather than "model confidence."

============================================================
16. TEST THIS ADVERSARIALLY
============================================================

Add deterministic tests demonstrating that these cannot become supported
claims:

1. value exists but on wrong entity

2. value exists but for wrong property

3. entity exists but wrong semantic role

4. user states an invented property

5. user states an invented connection

6. user provides the correct-looking value in the question

7. warning contains the same identifier/value

8. tool input contains the value but output does not

9. wrong unit

10. unsafe unit reinterpretation

11. reversed direction

12. neighboring entity mistaken for operated valve

13. process-side → utility-side false exchanger path

14. truncated traversal treated as complete

15. open end treated as known destination

16. fuzzy suggestion treated as resolved identity

17. ambiguous identifier silently selected

18. model adds unsupported explanatory engineering knowledge

19. prompt injection asks model to ignore graph

20. prompt injection asks for API key/system prompt

============================================================
17. POSITIVE GROUNDING TESTS
============================================================

Also prove legitimate answers still work.

Test:

exact property

connection

direction

path

pipe/segment

nominal diameter

equipment type

instrument relationship

open-end statement

absence of requested property

ambiguity response

multi-step traversal.

Do not overfit to only P4711/H1007.

============================================================
18. GENERALIZATION REGRESSION
============================================================

Abdullah's main concern is unseen questions.

Therefore inspect every new guardrail for accidental dataset/question-template
overfitting.

Do NOT add:

if "P4711" then...
if question contains "nominal diameter" then...
fixed known-question routes
known eval-answer mappings
question-specific prompt examples that leak evaluation cases.

Grounding should operate on STRUCTURED TOOL SEMANTICS, not known wording.

============================================================
19. HISTORICAL EVALUATION
============================================================

The existing 15/15 DeepSeek evaluation happened BEFORE this change.

Preserve it byte-for-byte.

Do not silently present it as validation of the new grounding architecture.

Do not modify:

saved answers

saved traces

gold answers

historical score

historical provider metadata.

README must distinguish:

historical frozen evaluation

from

post-evaluation deterministic grounding tests.

Do NOT run another formal provider evaluation during this task.

============================================================
20. UI
============================================================

Update the existing Streamlit UI only as necessary.

Instead of merely:

"Grounded against graph evidence"

make it possible to inspect:

GROUNDING STATUS

VALIDATED CLAIMS

EVIDENCE FOR EACH CLAIM

REJECTED CLAIMS if regeneration occurred

PROVENANCE

Keep the normal answer clean.

Put details under expanders.

This should make Abdullah able to SEE grounding, not just trust a green label.

============================================================
21. VISIBLE WORKFLOW
============================================================

Preserve:

tool calls

tool results

answer

grounding.

For a factual claim, the reviewer should be able to trace:

ANSWER CLAIM
↓
STRUCTURED CLAIM
↓
EVIDENCE ID
↓
GRAPH SOURCE

That is the standard I want.

============================================================
22. DOCUMENTATION
============================================================

Update documentation accurately.

README:

keep concise.

Change the limitation "Grounding is lexical" only if the new implementation
actually eliminates lexical matching as the primary grounding mechanism.

Do not claim "hallucination-proof."

Explain structured claim/evidence validation in a few sentences.

HOW_IT_WORKS:

teach the new grounding flow simply.

ARCHITECTURE_DEEP_DIVE:

document schemas, validator and remaining limitations.

SUBMISSION_AUDIT:

update grounding status.

DEMO_SCRIPT:

show how to inspect one claim's evidence.

============================================================
23. REMAINING LIMITATIONS
============================================================

Be explicit about what structured grounding still cannot prove.

Potential examples, only if accurate:

- claim extraction completeness;
- semantic equivalence outside known typed predicates;
- graph incompleteness;
- incorrect source P&ID data;
- planner may choose inefficient tools;
- absence in graph does not mean absence in physical plant.

I would rather have honest limitations than an inflated claim.

============================================================
24. DO NOT OVER-ENGINEER
============================================================

Do NOT add:

vector database

embedding-based grounding

external guardrails framework

another model

LLM-as-judge

Neo4j

ontology platform

policy engine

database

authentication

new deployment infrastructure.

This should be a focused hardening of the existing architecture.

============================================================
25. IMPLEMENTATION ORDER
============================================================

Do this in order:

1. audit existing evidence + grounding;
2. write failing deterministic tests for semantic grounding;
3. define/extend structured evidence;
4. define structured claims;
5. implement typed claim/evidence validation;
6. integrate synthesis;
7. integrate bounded regeneration/abstention;
8. add focused scope/injection guardrails;
9. update UI;
10. update docs;
11. run full deterministic tests;
12. run historical scorer OFFLINE only;
13. secret scan;
14. push normal commits.

============================================================
26. GIT
============================================================

The repository is already public.

Current remote:

https://github.com/shaaz1000/pid-graph-agent

Do not rewrite history.

Do not force-push.

Do not amend existing commits.

Create normal new commits.

Suggested logical commits:

feat: add structured claim grounding

test: add grounding and guardrail regressions

docs: document structured grounding model

Combine them if the changes are naturally inseparable, but do not manufacture
commit count.

No AI attribution.

Use existing Git identity.

Secret scan before pushing.

============================================================
27. VALIDATION
============================================================

Before push:

run all deterministic tests.

Run historical evaluation scorer OFFLINE.

Do not call Groq.

Do not call DeepSeek.

Confirm historical score is unchanged.

Run secret scan on:

tracked files

new commits/diff

history as appropriate.

Verify:

.env remains untracked.

Verify fresh clone/install if dependency/config changed.

============================================================
28. PUSH
============================================================

If and only if:

tests pass

historical scorer remains unchanged

secret scan passes

README claims are accurate

no historical artifacts changed

then push the new normal commits to main.

No force push.

============================================================
29. REPORT
============================================================

Return:

STRUCTURED GROUNDING HARDENING COMPLETE

A. BEFORE
- how grounding previously worked
- exactly what was lexical
- what was already structural

B. NEW GROUNDING MODEL
- evidence schema
- claim schema
- validator
- provenance

C. EXAMPLE
Show one real claim:

natural-language answer
→ structured claim
→ evidence
→ validation result

D. GUARDRAILS
- domain
- injection
- false premise
- tool allowlist
- live-state limitation

E. ADVERSARIAL TESTS
- categories
- results

F. POSITIVE REGRESSION
- results

G. TOTAL TESTS

H. HISTORICAL EVAL
- confirm unchanged
- explicitly state it predates this architecture

I. UI
- how I inspect claim → evidence

J. DOCUMENTATION

K. REMAINING LIMITATIONS

L. COMMITS

M. PUSH
- remote
- HEAD

N. SECURITY
- secret scan
- .env status

Then STOP.

Do not add more features.
