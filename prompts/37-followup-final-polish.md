Final submission polish only.

Do NOT change:
- agent code
- prompts
- graph logic
- evaluator logic
- gold answers
- historical evaluation artifacts
- holdout results

No more model runs.

We are preparing the repository for Sachin.

==================================================
1. ADD THE DIRECTIONAL-ROUTE LIMITATION
==================================================

Update the limitations section in:

docs/FOLLOWUP_EXERCISE.md

Add a concise limitation explaining:

A direction-agnostic route query can return a topologically valid path that is
not a valid process-flow interpretation.

Observed example:
T4750 -> SV 104.01 -> piping -> P4712

The graph contains this route when direction is ignored, but it traverses
backwards through the relief valve into the pump discharge.

Therefore:

- topological connectivity must not automatically be described as process flow;
- "direction=any" routes should be interpreted explicitly as graph connectivity;
- the current system can still choose this operation when a question asks
  whether a route "remains";
- this affected H5/HG2 and is related to the limitation seen in C7.

Do NOT fix it now.

Do NOT imply the graph is wrong.

Frame it as a semantic distinction between:
- undirected/topological reachability
and
- directional/process reachability.

Keep this to 1–2 concise sentences in the one-page report.

==================================================
2. MAKE THE FOLLOW-UP NOTE STRICTLY SHORT
==================================================

Sachin asked for a short note under a page.

Create a concise version that can realistically fit on one page of normal text.

Target approximately 500–700 words maximum.

Keep detailed tables/results outside the main note.

Structure:

# Follow-up Exercise

## What changed
2–3 short paragraphs:
- structured request decomposition
- generic multi-step graph analyses
- structured direct/derived/unknown answer contract
- semantic regex removed from the primary grounding path

## What was tested
Very compact:
- 27 complex questions
- 10 paraphrase groups
- 41 phrasings
- 3 repeats each
- 150 scheduled runs
- Nemotron 3 Super via NVIDIA
- no paid inference

## Results
Use a tiny table or compact bullets:

Complex:
- mean 0.64
- 11 correct / 11 partial / 3 incorrect / 2 withheld

Consistency:
- 22/41 repeat-consistent
- 1/10 groups fully cross-phrasing consistent
- required-fact recall 0.70
- 0 contradictions
- 0 rendered facts outside tool evidence
- 0 model-authored factual prose shown

## What still fails
Only the important points:
- planner/tool-selection variance
- early stopping on multi-hop questions
- retrieved facts sometimes omitted from final structured answer
- directional vs direction-agnostic route ambiguity
- open-weight vs OSI-open-source licence distinction

## Time
State the actual approximate follow-up time honestly.

Then link to:
- full evaluation artifacts
- detailed machine-readable results
- holdout sanity check

Do not put giant per-question tables in this one-page note.

If detailed information currently lives in docs/FOLLOWUP_EXERCISE.md,
either:
A. make that file the concise one-page report and move detailed tables to a
   separate appendix file,
or
B. keep the detailed file and add a clearly named one-page summary such as:
   docs/FOLLOWUP_SUMMARY.md

Prefer the structure that makes Sachin's requested deliverable obvious.

==================================================
3. COMMIT THE HOLDOUT AS A POST-EVALUATION CHECK
==================================================

Commit the holdout artifacts.

Label them clearly as:

POST-EVALUATION HOLDOUT / SANITY CHECK

They must not be presented as part of the official 150-run score.

Document:

Current hardened SHA:
fd4dfe8022b45fe7833f7ff517a0533b217913d9

Holdout:
- 8 fresh complex questions
- 3 fresh complex paraphrase groups
- 4 phrasings per group
- 2 repeats each
- 32 scheduled inference runs
- 31 answered
- 1 provider timeout

Complex holdout:
- 5 correct
- 2 partial
- 1 incorrect
- mean 0.78
- required-fact recall 18/22
- required-unknown recall 1/1
- 0 contradictions
- 0 unsupported facts

Paraphrase holdout:
- 10/12 phrasings repeat-consistent on required facts
- HG1 fully consistent on required facts
- HG3 consistent in 7/8 answered runs
- HG2 consistently exposed the directionality problem and must NOT be described
  as successful merely because the raw consistency metric says so

Security/provenance:
- 0 model-authored prose in rendered answers
- 0 cited ids missing from tool results
- 0 model-controlled tool-input text leaked into rendered output

State explicitly:

"The holdout was created and frozen before inference. No code, prompt or gold
changes were made after results were observed."

==================================================
4. DO NOT OVERSELL HG2
==================================================

The evaluator's raw consistency result for HG2 is misleading.

Do not say:
"HG2 was consistent."

Instead say:

"HG2 exposed a semantic weakness: direction-agnostic connectivity can be stable
across paraphrases while still answering the wrong process-level question."

This is an important distinction between:
- consistency
and
- correctness.

==================================================
5. README FINAL POLISH
==================================================

Keep README concise.

Add or update:

## Follow-up Evaluation

Include:
- link to one-page summary
- link to detailed follow-up artifacts
- link to post-evaluation holdout

One sentence for the holdout:

"A separate frozen holdout on the hardened final branch used 8 new complex
questions and 3 new paraphrase groups; it found no grounding/security
regressions but reproduced the directional-vs-topological route limitation."

Do not add all holdout tables to README.

==================================================
6. COMMITS
==================================================

Create logical commits only.

Suggested:

eval: add post-evaluation holdout sanity check

docs: finalize follow-up summary and limitations

Do not squash.

No AI attribution lines.

==================================================
7. FINAL VERIFICATION
==================================================

Run:

- full deterministic tests
- secret scan
- git status
- origin/main comparison

Do NOT run NVIDIA again.

Report:

- holdout commit hash
- docs commit hash
- final test count
- exact one-page summary path
- exact detailed-results path
- exact holdout path
- confirmation official 150-run artifacts unchanged
- confirmation evaluated SHA remains 87953f4
- confirmation holdout was on fd4dfe8
- working tree clean
- origin/main == local HEAD

Then STOP.

Do not email Sachin.
