Approved.

Proceed with the finalization exactly in this order.

Do NOT rerun the evaluation.

==================================================
1. COMMIT THE EVALUATION ARTIFACTS UNCHANGED
==================================================

The recorded follow-up evaluation is authoritative:

Evaluated commit:
87953f481aa3c1273cdb34f8ea200ed0ba41d50a

150 scheduled runs:
- 27 complex-question runs
- 123 consistency runs
- 1 provider failure

Do not alter:
- run files
- answers
- scores
- classifications
- gold
- question sets
- consistency calculations

Commit the evaluation artifacts exactly as produced.

Suggested commit:

eval: record complex and paraphrase follow-up results

Preserve the provider failure as-is.

==================================================
2. POST-EVALUATION STATUS-MESSAGE SECURITY FIX
==================================================

After the evaluation artifact commit, fix the trust-boundary issue.

Problem:

A tool status row may currently echo model-controlled tool input.

Example class:
"No entity in the P&ID graph matches '<model supplied query>'"

If that row is cited, model-controlled text can become visible as if it were
evidence.

The evaluation audit found:
- 5 cited status rows
- 2 contained input text not present in the user question
- both were harmless canonical-ish values
- no injected prose reached any evaluated answer

So:
the vulnerability is real,
but it did NOT contaminate the recorded follow-up evaluation.

==================================================
SECURITY DESIGN
==================================================

Do not solve this with prose filtering or another semantic regex.

Prefer fixed application-rendered status templates.

Model-controlled tool arguments must NOT automatically become user-visible
evidence.

Allowed visible provenance should come only from:

A. text directly present in the user's question
B. canonical graph data
C. deterministic application wording

For a status such as not_found:

Internal representation may retain:
- query
- entity type
- status

But rendering should prefer:

"No matching entity was found in the P&ID graph."

Only include a quoted identifier/name if the application can establish that it
comes from:
- the user's question, or
- a canonical graph item

Do NOT trust the tool argument merely because the tool returned it.

==================================================
REGRESSION TESTS
==================================================

Add deterministic tests for:

1. safe user-originated identifier
2. safe canonical graph entity
3. model-invented sentence used as a lookup query
4. model-invented process claim used as lookup query
5. punctuation/control-token injection
6. harmless unknown type/name
7. status row cited in final answer

For unsafe model-originated inputs:
none of the input prose may appear in the rendered answer.

No LLM judge.
No semantic regex.

==================================================
PROVENANCE
==================================================

Document clearly:

"The follow-up evaluation was run on commit 87953f4. A post-evaluation security
review identified a status-message provenance issue. No evaluated answer
contained injected model prose. The rendering path was hardened afterward in a
separate commit."

Do not imply the hardened code produced the recorded evaluation.

Suggested commit:

fix: prevent model-controlled status text from reaching answers

==================================================
3. WRITE THE FOLLOW-UP REPORT
==================================================

Create:

docs/FOLLOWUP_EXERCISE.md

Keep the narrative section under approximately one page.

Use the actual results without trying to improve or soften them.

Structure:

# Follow-up Exercise

## What was tested

Sachin asked for:
- more complex operational P&ID questions
- consistency under rephrasing
- automation of consistency measurement
- reduced reliance on regex for semantic grounding

Explain that the follow-up path now uses:

question
→ structured request decomposition
→ generic graph tools
→ direct graph facts / deterministic derived facts / typed unknowns
→ schema validation
→ application-rendered answer

No model-authored factual prose is shown in the scored path.

Regex remains only where appropriate for lexical/protocol/legacy functions,
not as the primary semantic-grounding mechanism.

==================================================
4. REPORT THE COMPLEX RESULTS EXACTLY
==================================================

Use:

27 questions
- 11 fully correct
- 11 partial
- 3 incorrect
- 2 withheld
- mean score 0.64

Provided C1-C15:
- 5 correct
- 9 partial
- 0 incorrect
- 1 withheld
- mean 0.67

Own 12:
- 6 correct
- 2 partial
- 3 incorrect
- 1 withheld
- mean 0.60

Required facts:
82 / 128

Required unknowns:
4 / 8

Main failure causes:
- incomplete traversal: 6
- planner/tool choice: 6
- grounding rejection: 2
- answer synthesis: 1
- entity resolution: 1

Do NOT call this a high score.

Explain that the complex suite exposed planning depth and tool-selection
variance that was not visible in the earlier simple eval.

==================================================
5. REPORT CONSISTENCY EXACTLY
==================================================

10 groups
41 phrasings
3 repeats
123 scheduled runs

Report:

- repeat-consistent phrasings: 22 / 41
- fully cross-phrasing-consistent groups: 1 / 10
- required-fact recall: 0.70
- entity resolution consistent: 7 / 10 groups
- contradictions: 0
- descriptive cited-fact Jaccard: 0.44

Per-run:
- 58 correct
- 43 partial
- 18 incorrect
- 3 withheld
- 1 provider failure

Provided groups:
- recall 0.56
- pair agreement 0.22

Own groups:
- recall 0.79
- pair agreement 0.52

Do not collapse consistency and correctness into one number.

Explicitly distinguish:

1. repeat consistency
2. paraphrase consistency
3. semantic correctness

==================================================
6. EXPLAIN THE MAIN FINDING
==================================================

The strongest conclusion is NOT:

"the agent is consistent."

That would be false.

The correct conclusion is:

"The structured grounding path remained safe and contradiction-free, but the
planner was not sufficiently stable under complex multi-step phrasing. Most
inconsistencies came from retrieving or citing different subsets of valid graph
facts, rather than from contradictory facts."

Support with the observed causes:

65 incomplete consistency runs:
- answer synthesis / retrieved but not cited: 27
- planner/tool choice: 18
- incomplete traversal: 11
- entity resolution: 5
- grounding rejection: 3
- provider: 1

Mention recurring examples:

- R1 often found all four boundary valves but omitted the relief-line fact
- R2/G2 often did not test reachability after closing a valve
- R3 often stopped at the controller's immediate links

Do not add fixes now.

==================================================
7. GROUNDING / TRUST SECTION
==================================================

Report:

- 144 structured answers from 149 answered runs
- 5 withheld
- 0 cited facts absent from tool results
- 0 model-authored prose shown
- 0 contradictions
- 300 requested outputs accounted for
- 268 covered by facts
- 42 covered by typed unknowns
- 18 rejected submissions handled by normal retry/repair
- 6 final repairs attempted
- 6 final repairs succeeded

Important wording:

Do NOT say:
"zero hallucinations"

Use:

"No rendered answer cited a fact outside its tool evidence, and no model-authored
factual prose was shown."

Also state that this property is enforced structurally by the follow-up answer
contract.

==================================================
8. INFRASTRUCTURE
==================================================

Report:

Model:
nvidia/nemotron-3-super-120b-a12b

License wording:
"open-weight model released under the NVIDIA Nemotron Open Model License"

Do NOT call it OSI open source.

Report:

- 1,013 model calls
- 698 graph tool calls
- 6.43M tokens
- 1h45m wall time
- 1 provider failure
- complex median latency 43.9s
- complex mean 54.7s
- consistency median 24.5s
- consistency mean 30.3s

Infrastructure note:

"Evaluation used the existing NVIDIA-hosted Nemotron 3 Super endpoint. No paid
inference service or provider upgrade was required."

==================================================
9. LIMITATIONS
==================================================

Keep this candid and concise.

Include:

- planner/tool selection is the dominant limitation
- multi-hop traversals frequently terminate too early
- answer construction sometimes omits retrieved facts
- entity resolution is not fully stable under indirect/property-based phrasing
- unknown/not-in-drawing coverage is incomplete
- hosted model/provider variance exists
- evaluation was performed on the reference C01 follow-up set, not a blind
  process-engineer benchmark
- Nemotron is open-weight rather than OSI-open-source

Do not propose dozens of future features.

A short production-next-step paragraph is enough:

- reduce planner freedom through a typed planning/capability layer
- use composite deterministic graph analyses for common multi-hop operations
- preserve the structured answer contract

==================================================
10. README
==================================================

Add a concise section:

## Follow-up: Complex Reasoning and Rephrasing

Include only:
- why the follow-up was added
- 27 complex questions / 0.64 mean
- 10 rephrasing groups / 22 of 41 repeat-consistent / 1 of 10 fully
  cross-phrasing-consistent
- 0 contradictions
- 0 model-authored factual prose shown
- link to docs/FOLLOWUP_EXERCISE.md

Do not crowd the README with all detailed tables.

==================================================
11. TIME SPENT
==================================================

The follow-up asked for roughly 4 hours.

Report the actual follow-up time honestly.

Do not invent a number.

Break it down only if the repository/history gives enough evidence to do so.

If exact time cannot be derived, use a truthful approximate statement.

==================================================
12. FINAL COMMITS
==================================================

Expected logical history:

1. eval: record complex and paraphrase follow-up results
2. fix: prevent model-controlled status text from reaching answers
3. docs: report follow-up exercise results

Run:
- full deterministic tests
- secret scan
- git status
- origin/main comparison

Do NOT rerun the 150-run evaluation after the security fix.

==================================================
13. FINAL REPORT TO ME
==================================================

Return:

- evaluation-artifact commit hash
- security-fix commit hash
- docs commit hash
- final deterministic test count
- confirmation historical evaluation artifacts unchanged
- confirmation evaluated SHA remains 87953f4
- status-row audit result
- final security regression result
- README/report summary
- git status
- origin/main == local HEAD

Then STOP.

Do not email Sachin.
