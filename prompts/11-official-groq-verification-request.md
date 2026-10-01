Proceed with the frozen M2.2b official Groq verification.

The implementation is frozen at:

a8d56b312e831d7ace33a267f251a9171e62f1d1

Do not modify any source code, prompts, tools, tests, configuration files,
graph logic, grounding, traversal, compaction or provider behavior.

Do not run DeepSeek.

Do not start M3.

1. Confirm:

git rev-parse HEAD
git status --short

HEAD must be:
a8d56b312e831d7ace33a267f251a9171e62f1d1

The working tree must be clean.

2. Use explicit runtime overrides:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

Do not edit .env.

3. Make ONE minimal Groq capacity check.

If the capacity check indicates there is not enough quota to safely complete
the frozen five-question run:

STOP.

Do not partially run the verification.
Do not repeatedly probe Groq.

Report the exact infrastructure status without exposing credentials.

4. If sufficient capacity is available, run the existing frozen five-question
official M2.2 verification set exactly ONCE.

Do not change the questions.

Do not retry semantic failures.

Do not change anything between questions.

If an individual question is incorrect, partial, abstained or rejected by
grounding, record it and continue unchanged.

5. For each question record:

- exact question
- provider
- model
- frozen commit
- final answer
- complete tool sequence
- model-call count
- tool-call count
- prompt tokens
- completion tokens
- total tokens
- latency
- grounding result
- unsupported claims
- regeneration used
- fallback used
- outcome

Outcome must be one of:

correct
partially_correct
incorrect
abstained
infrastructure_failure

Judge factual correctness against deterministic graph evidence.

A provider failure is not an agent correctness failure.

6. Specifically inspect:

REACHABILITY
- adjacency vs reachability
- multiple downstream destinations
- terminal vs truncated frontier
- continues_beyond_max_depth
- through_equipment
- unsupported claims

INSTRUMENTATION
- relationship composition
- related instrument resolution
- failAction retrieval
- alias guessing/redundant lookups

PROPERTY/GROUNDING
- chamber attribution
- engineering values
- minus/dash normalization
- unsupported property claims
- false grounding rejection

7. After ALL five have run, calculate:

- correct
- partially correct
- incorrect
- abstained
- infrastructure failures
- total/average tokens
- total/average prompt tokens
- total/average completion tokens
- total/average model calls
- total/average tool calls
- grounding regenerations
- fallbacks
- turn-limit hits
- redundant calls where observable

Do not rerun anything after calculating the results.

8. Recommend exactly one:

READY_FOR_M3

or

BLOCKING_GENERALIZATION_ISSUE

A perfect 5/5 is NOT required for READY_FOR_M3.

Do not recommend reopening development for ordinary model variance,
non-critical inefficiency, cosmetic wording, or an honestly disclosed edge
case.

BLOCKING_GENERALIZATION_ISSUE should require evidence of a repeatable,
general architectural problem likely to affect unseen questions.

9. Return:

PROJECT PROGRESS

✓ M1 — Deterministic graph foundation
✓ M2 — Multi-step LLM agent
✓ M2.1 — Agent stabilization
✓ M2.2a — DeepSeek diagnostic
✓ M2.2 final stabilization
✓ M2.2 hygiene

✓/! M2.2b — Official Groq verification
  Frozen commit: a8d56b3
  Provider: groq
  Model: openai/gpt-oss-20b
  Result: <summary>

→ M3 — Formal evaluation
  Recommendation: <READY_FOR_M3 / BLOCKING_GENERALIZATION_ISSUE>

Then provide:

A. PRE-RUN FREEZE CHECK
B. CAPACITY CHECK
C. FIVE OFFICIAL RESULTS
D. REACHABILITY REVIEW
E. INSTRUMENTATION REVIEW
F. PROPERTY/GROUNDING REVIEW
G. AGGREGATE METRICS
H. FAILURES OR LIMITATIONS
I. GIT STATUS
J. RECOMMENDATION

Then STOP.

Do not fix anything.
Do not start M3.
Do not start M4.
Do not push.
