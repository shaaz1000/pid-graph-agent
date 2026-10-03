Approved.

Proceed with the four GENERIC validator fixes only, then run one clean full
37-question cross-P&ID evaluation.

The objective is now to establish a defensible post-fix generalization baseline.
Do not expand scope beyond that.

==================================================
1. FIX THE FOUR GENERIC VALIDATOR DEFECTS
==================================================

Implement fixes for exactly these four issues:

BUG 1 — identifiers/tags containing spaces
Example:
K 2750

Current problem:
the numeric portion is treated as an independent value and can be associated
with the wrong evidence item.

Required behavior:
when a token/value appears as part of a complete identifier and the cited
evidence unambiguously associates that complete identifier with the referenced
entity, do not treat the internal numeric token as an independent unsupported
fact.

The rule must be generic.
Do not special-case K 2750 or C02.

--------------------------------------------------

BUG 2 — non-ASCII identifiers

Example:
PIS⁺Z⁺A275003

Current problem:
answer-side tokenization and evidence-side tokenization disagree.

Required behavior:
use a common normalization/tokenization strategy for identifiers on BOTH sides.

It must preserve enough identity information to distinguish entities correctly.

Test:
- superscript/non-ASCII identifier
- ordinary ASCII identifier
- ensure normalization does not cause two distinct identifiers to collapse

Do not special-case this particular tag.

--------------------------------------------------

BUG 3 — relation words inside entity names

Example:
ActuatingFunction-1 causing the validator's "operates" / relation detector
to infer the wrong relation subject.

Required behavior:
entity identifiers/names must not be interpreted as natural-language relation
phrases.

Mask or protect recognized entity mentions before relation-word detection,
or implement another general equivalent.

Do not special-case ActuatingFunction.

Tests must verify:
- relation word inside entity/type name does not trigger relation detection
- actual prose relationship still does trigger it

--------------------------------------------------

BUG 4 — shared loop/identifier values

Example:
loop number 031 appearing on multiple related instrumentation functions.

Current problem:
the validator rejects the value as ambiguous even when cited evidence explicitly
shows the named entities share that identifier.

Required behavior:
an identifier/value may legitimately belong to multiple entities.

If the sentence names the relevant entities and the cited facts demonstrate that
the shared identifier belongs to those entities in the claimed role, accept it.

Do not globally relax ambiguity handling.

The validator must still reject cases where:
- a value exists elsewhere in evidence but not for the named entity
- a diameter/property is incorrectly transferred between entities
- an ambiguous identifier is cited without enough relationship evidence

==================================================
2. TEST REQUIREMENTS
==================================================

Add deterministic regression tests for all four fixes.

Also retain and run all existing adversarial grounding tests.

Critical regressions that MUST continue to fail validation:

- assigning DN 80 from one line to another entity/line
- invented entity identifiers
- invented line identifiers
- unsupported relationships
- reversed relationship direction where direction matters
- unsupported property values
- citation IDs that do not exist

The fixes must REDUCE FALSE REJECTIONS without increasing FALSE ACCEPTANCES.

Report test count before running live evaluation.

==================================================
3. DO NOT FIX THE P04 PARTIAL
==================================================

Do NOT change the agent because it failed to challenge the false "DN 150"
premise.

That is a legitimate reasoning/synthesis limitation and should remain in the
evaluation.

Do not add prompt wording aimed at that particular question.

==================================================
4. PRESERVE THE SMOKE RUN
==================================================

Keep the existing 16-question smoke artifacts unchanged as:

PRE-FIX CROSS-P&ID SMOKE TEST

They are useful evidence showing that unseen datasets exposed four generic
validator defects.

Do not overwrite them.

==================================================
5. RUN ONE CLEAN FULL CROSS-P&ID EVALUATION
==================================================

After fixes + offline tests pass, run all 37 questions from the eight suites:

- c02
- c03
- i03
- i05
- e12
- e06
- p02
- p04

Use:
NVIDIA-hosted nvidia/nemotron-3-super-120b-a12b

One run per question.

No manual intervention.
No question rewrites.
No evaluation-time code changes.
No automatic model switching.
No per-dataset prompts.
No question-specific routing.

The accepted C01 baseline remains untouched and must NOT be rerun.

==================================================
6. REPORT PER-DATASET RESULTS
==================================================

For each of the eight suites report:

- questions
- fully correct
- partial
- incorrect/withheld
- points
- weighted score
- grounded
- limited
- unsupported claims
- parser failures
- graph abstraction failures
- entity resolution failures
- planning failures
- answer synthesis failures
- grounding validator failures
- provider failures
- median latency
- mean latency
- LLM calls
- graph tool calls

Then report:

CROSS-P&ID AGGREGATE
excluding C01

- total questions
- fully correct
- partial
- incorrect
- weighted score
- grounded
- limited
- unsupported final claims
- total latency
- median latency
- mean latency

Keep the original C01 result separately:

C01 BASELINE
15 questions
12 fully correct
13.42 / 15
0.894 mean
14 grounded
1 limited
0 unsupported claims

Do NOT merge these into a misleading single score.

==================================================
7. GENERALIZATION CLAIM
==================================================

After the run, answer explicitly:

Did the same:

- ProteusSerializer
- GraphLoader
- GraphAbstractor
- normalizer
- GraphService
- entity resolver
- graph tools
- LangGraph workflow
- grounding validator

operate across all tested P&IDs without dataset-specific logic?

State any qualifications precisely.

Expected qualification currently:

- SignalLineFunction required one generic schema mapping.
- Validator required four generic robustness fixes discovered by unseen
  identifiers/structures.

Do not describe these as dataset-specific fixes.

==================================================
8. ALL-35 INGESTION RESULT
==================================================

Preserve and document separately:

35 / 35 official DEXPI 1.3 files successfully complete:

ProteusSerializer
→ GraphLoader
→ GraphAbstractor
→ normalize
→ GraphService

with the XML files unchanged.

Report remaining dropped links/warnings honestly.

Do NOT claim that all 35 received live LLM evaluation.

Use accurate wording:

"All 35 official DEXPI 1.3 examples were exercised through the deterministic
ingestion/graph pipeline; eight structurally diverse datasets were selected for
live agent reasoning evaluation."

==================================================
9. AFTER THE FULL RUN
==================================================

Do NOT automatically fix any failures from the 37-question evaluation.

Preserve them.

Classify each failure:

A LLM planning
B entity resolution
C graph retrieval
D graph abstraction/schema
E direction semantics
F missing source data
G answer synthesis
H grounding validator
I evaluation expectation
J parser/schema compatibility

If a question fails, record it and move on.

We are measuring generalization now, not optimizing against the benchmark.

==================================================
10. DOCUMENTATION
==================================================

After the run, update README with a concise section:

## Cross-P&ID Generalization

Include:

- Sachin's concern translated into the technical objective:
  testing beyond one reference P&ID
- 35/35 ingestion result
- eight selected datasets and why they are structurally different
- cross-P&ID evaluation table
- C01 baseline separately
- SignalLineFunction schema variation discovered and fixed generically
- four validator robustness issues found in smoke testing and fixed generically
- remaining failures/limitations
- source and CC BY 4.0 attribution

Keep it concise.

Do not turn README into a research paper.

==================================================
11. COMMITS
==================================================

Once the full run is complete and results are documented:

Create logical commits, for example:

1.
fix: support DEXPI signal-line variation across datasets

2.
fix: harden grounding validator for diverse identifiers

3.
feat: add cross-P&ID evaluation datasets and ingestion matrix

4.
docs: report cross-P&ID generalization results

Preserve real history.
Do not squash.

Ensure:
- no API key
- no .env
- no generated secrets
- source XML attribution present

Push normally to main.

==================================================
12. STOP CONDITIONS
==================================================

After push, report:

- final test count
- 35-file ingestion result
- eight-dataset cross-P&ID score
- per-dataset scores
- unsupported claim count
- remaining failures
- final commit hashes
- git status
- confirmation origin/main == local HEAD

Then STOP.

Do not:
- run more datasets
- rerun C01
- optimize individual failed questions
- switch models
- add OCR
- host the app
- email Sachin
- make unrelated improvements

I will review the final result before we reply to Sachin.
