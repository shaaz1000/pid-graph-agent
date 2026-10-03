The review surfaced a few issues worth addressing before technical review.

We are NOT reopening the architecture or evaluation.

The accepted evaluation artifacts remain frozen:

C01:
- 15 questions
- 0.894

Cross-P&ID:
- 37 questions
- 30/37
- 0.811

Do NOT rerun or modify those results.

We are doing one narrowly scoped POST-EVALUATION HARDENING pass.

==================================================
1. FIX THE HEDGE-WORD RELATION BYPASS
==================================================

You reproduced this as incorrectly grounded:

"If you follow the piping, H1007 feeds P4711. [E1.3]"

because the presence of a disclaimer/hedge word causes relation validation to be skipped.

Fix this generically.

A hedge/disclaimer word must NOT disable relationship validation for the entire sentence.

The validator should still determine whether:

subject
relation
object
direction

are supported by the cited evidence.

Add regression tests showing:

FAIL:
"If you follow the piping, H1007 feeds P4711."

PASS only if supported:
"If you follow the piping, P4711 feeds H1007."

Also preserve legitimate disclaimer behavior where needed.

Do not special-case H1007/P4711.

==================================================
2. HANDLE RELATION SYNONYMS GENERICALLY
==================================================

You reproduced:

"H1007 sends fluid to P4711."

as passing because "sends fluid to" is outside the current relation vocabulary.

Do NOT attempt unrestricted semantic NLP.

Instead introduce a small generic relation vocabulary / alias table for topology relations, for example:

feeds
supplies
discharges to
sends fluid to
flows to
upstream of
downstream of
connected to
operates
actuates
controls
senses
measures at

Map aliases into canonical relation types.

Direction must still be validated.

Keep the implementation data-driven rather than a long chain of if statements.

Add positive and negative direction tests.

Do not add question-specific phrases.

==================================================
3. UNSUPPORTED FACTUAL PROSE WITHOUT IDENTIFIERS
==================================================

You reproduced:

"It is the main cooling water pump."

as passing because the sentence contains no identifier/number that the validator extracts.

We should not claim that the validator grounds a sentence like this.

Implement the smallest safe generic behavior.

Preferred behavior:

If a model sentence appears factual but contains no checkable entity/value/relation that can be tied to cited evidence, it must NOT receive the strongest grounded status.

It may become:
- limited
or
- insufficient_evidence

depending on the existing contract.

Do not attempt to solve arbitrary natural-language truth verification.

Do not introduce another LLM judge.

Add tests for:
- invented purpose
- unsupported role
- ordinary non-factual connective prose
- evidence-supported factual sentence

==================================================
4. DO NOT TOUCH THESE YET
==================================================

Do NOT fix:
- empty E<n>.0 evidence ids
- chained instrumentation validation
- dotted line-number extraction
- normalized spelling H1008 vs H-1008
- connector composition links
- multi-hop planning
- LangGraph architecture
- structured-triple redesign

Those remain documented limitations.

==================================================
5. DOCUMENTATION CORRECTIONS
==================================================

Update stale documentation only where factually wrong.

Specifically inspect and fix:

README:
- 556 tests -> current real count
- make --pid usage visible in "How to run"
- make cross-P&ID reproduction discoverable
- review claims such as:
  "All factual answers are derived..."
  "a stated relation must..."
  "0 unsupported claims"

Use precise wording.

Do not claim the validator proves truth.

Preferred framing:

"Plant-specific facts are retrieved from deterministic operations over the pyDEXPI graph. A deterministic grounding validator checks cited identifiers, values and supported relation classes before model-generated prose is shown."

For evaluation wording:

"0 unsupported claims were detected in final answers by the evaluation/grounding checks used for the recorded run."

Do not write "zero hallucinations."

Also correct stale supporting docs:
- docs/DEMO_SCRIPT.md
- docs/ARCHITECTURE_DEEP_DIVE*
- docs/SUBMISSION_AUDIT.md

Remove obsolete DeepSeek 15/15/current-provider statements where they are presented as current results.

Preserve historical results if explicitly labelled historical.

==================================================
6. TESTS ONLY — NO NVIDIA
==================================================

Run the full offline deterministic test suite.

Do NOT rerun:
- C01 NVIDIA evaluation
- 37-question NVIDIA evaluation

The recorded scores belong to the evaluated commits and remain unchanged.

==================================================
7. PROVENANCE
==================================================

Make it explicit in README or evaluation docs:

"The published evaluation results were produced before the post-evaluation validator hardening below. Evaluation artifacts are preserved unchanged."

Do not imply the hardened code produced the 0.894 / 0.811 scores.

==================================================
8. REVIEW CLAIMS AGAIN
==================================================

After changes, try these adversarial sentences offline against representative evidence:

1. reversed feed relation with "if"
2. reversed relation using "sends fluid to"
3. unsupported purpose such as "main cooling water pump"
4. correct feed relation
5. correct control/operate relation
6. unsupported operating state
7. wrong diameter assigned to another line
8. invented entity

Report whether each is:
- grounded
- limited
- rejected

The unsafe examples must not receive grounded.

==================================================
9. COMMIT/PUSH
==================================================

If all offline tests pass:

Create separate logical commits:

fix: harden relation grounding checks

docs: align submission documentation with final evaluation

Push normally.

Do not squash.

Then report:
- files changed
- test count
- adversarial results
- documentation corrections
- commit hashes
- git status
- confirmation evaluation artifacts unchanged

STOP.

Do not email Intuigence.
Do not make further architectural improvements.
