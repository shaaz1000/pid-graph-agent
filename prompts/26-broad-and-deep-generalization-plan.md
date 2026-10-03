Sachin's feedback was:

"Can you please do it for more Dexpi Files (if not already done)?
A single file is not a strong indicator of performance.
You can find more dexpi files online."

I do NOT want to interpret "more" too narrowly.

We should demonstrate BOTH:

1. BROAD INGESTION GENERALIZATION across many real DEXPI files.
2. DEEP AGENT REASONING GENERALIZATION across a representative subset.

Current discovery:
- Official DEXPI e.V. TrainingTestCases contains 35 DEXPI 1.3 XML files.
- All 35 already load successfully through the unchanged:
  ProteusSerializer
  -> GraphLoader
  -> GraphAbstractor
  -> normalize
  -> GraphService
  pipeline.
- C02 and C03 are complete P&IDs.
- E-series are equipment examples.
- I-series are measurement/control examples.
- P-series are piping examples.

This is now our target strategy.

==================================================
PART A — ALL-FILE INGESTION MATRIX
==================================================

Use ALL 35 official DEXPI 1.3 files.

For every file, run deterministic/offline ingestion only.

Produce a machine-readable and README-friendly table containing:

- dataset/file name
- source
- DEXPI/Proteus version if identifiable
- parse success/failure
- GraphLoader success/failure
- GraphAbstractor success/failure
- normalization success/failure
- GraphService construction success/failure
- plant graph node count
- plant graph edge count
- conceptual graph node count
- conceptual graph edge count
- equipment count
- piping component count
- instrumentation count
- line count
- tagged entity count
- untagged entity count
- connected component count
- number/type of dropped or unsupported links
- warnings

The goal is to be able to truthfully say something like:

"The same ingestion and graph abstraction pipeline was exercised against all 35 official DEXPI 1.3 example files."

Do not claim reasoning performance from this matrix.
It only demonstrates ingestion/abstraction compatibility.

Do not modify source XML files.

==================================================
PART B — REPRESENTATIVE LIVE GENERALIZATION SUITE
==================================================

We should NOT pay NVIDIA cost for all 35 files.

Select approximately 6–8 datasets that maximize structural diversity.

The selection should cover these categories:

1. Complete process P&ID
2. Complete piping-heavy P&ID
3. Single-equipment example
4. Piping example
5. Instrumentation/control example
6. File with no normal equipment tags
7. File exposing SignalLineFunction
8. File containing ambiguity, missing fields or unusual naming if possible

C02 and C03 must be included.

I03 should be included because it exposes the SignalLineFunction variation.

From E-series, P-series and other I-series, inspect profiles and select the most structurally useful examples.

Do NOT select files merely to increase the count.

For every chosen dataset explain:
- why it was selected
- what structural behavior it tests that another dataset does not

Target approximately:

6–8 datasets total
x
4–6 questions each

Rough target:
25–40 new live evaluation questions.

Do NOT run them yet.

First show me the proposed selection and questions.

==================================================
PART C — QUESTION DESIGN
==================================================

Every dataset's questions must be generated from deterministic inspection of that graph.

Do NOT invent expected facts from the LLM.

Expected answers must come from:
- find_entities
- get_entity
- get_connections
- traverse
- find_path
- get_properties
- list_entities
or direct deterministic GraphService inspection.

For each selected file include a mix of whichever categories actually exist:

- entity lookup
- type/description lookup
- direct connection
- multi-hop path
- upstream/downstream traversal
- line/property lookup
- equipment enumeration
- instrumentation relationship
- ambiguity
- missing information
- adversarial unsupported assumption
- cross-dataset leakage test

Not every file needs every category.

Avoid trivial questions where possible.

We want to test whether the SAME agent can reason over graphs with different structure and naming conventions.

==================================================
PART D — DATASET SELECTION MUST BE GENERIC
==================================================

Add a generic dataset-selection mechanism.

Preferred:

pid-agent --pid path/to/file.xml "question"

Also support the same through evaluator.

Do not create:

if dataset == "C02":
...
if dataset == "I03":
...

No dataset-specific code branches.

No file-specific prompts.

No tag-specific routing.

No expected-answer-specific logic.

The SAME:
- loader
- graph abstraction
- entity resolver
- graph service
- tools
- LangGraph workflow
- grounding validator
must operate across every dataset.

==================================================
PART E — GENERIC SCHEMA FIXES
==================================================

You identified SignalLineFunction as a genuine DEXPI variation currently dropped by the normalizer.

I approve fixing this GENERICALLY.

Map SignalLineFunction into the same internal signal-link abstraction as the equivalent supported signal type.

Requirements:
- no I03-specific branch
- add tests using at least two files/classes if possible
- preserve existing behavior
- show before/after result

Do NOT fix other warnings unless they materially block reasoning across several datasets.

For example:
- placeholder line numbers: source-data limitation, do not fix
- drawing-direction ambiguity: document
- connector-reference categorization: only fix if it causes material cross-file failures

==================================================
PART F — KEEP C01 BASELINE IMMUTABLE
==================================================

The existing C01 baseline remains untouched:

- 15 questions
- 12 fully correct
- 13.42/15 weighted
- mean 0.894
- 14 grounded
- 1 limited
- 0 unsupported claims

Do not rerun it.
Do not alter its artifacts.
Do not merge its score into the new cross-file evaluation without clearly separating it.

==================================================
PART G — EVAL ARTIFACT STRUCTURE
==================================================

Generalize the evaluator so runs are namespaced by dataset.

Something like:

evals/
  datasets/
    c01/
    c02/
    c03/
    eXX/
    iXX/
    pXX/

Each dataset should have:
- questions.json
- expected/gold facts
- run.json
- transcripts/
- score summary

The evaluator must accept:
- --pid
- --questions
- --dataset-name

Default behavior should still work for C01.

==================================================
PART H — SCORING
==================================================

For every live-tested dataset report:

- questions
- fully correct
- partial
- incorrect
- weighted score
- grounded
- limited
- unsupported claims
- parser failures
- graph abstraction failures
- entity resolution failures
- planning failures
- answer synthesis failures
- grounding failures
- provider failures
- median latency
- mean latency
- LLM calls
- graph tool calls

Then provide:

1. Per-dataset scores.
2. Cross-P&ID aggregate excluding C01.
3. Original C01 baseline separately.
4. Overall descriptive summary across all files.

Do not hide weak datasets.

==================================================
PART I — MOST IMPORTANT CLAIM TO VERIFY
==================================================

At the end we need evidence for this statement:

"The same graph ingestion, normalization, entity resolution, graph tools, agent workflow and grounding validator were exercised across previously unseen DEXPI files without dataset-specific logic."

Determine whether that statement is fully true.

If it is not, explain exactly what changed and why.

==================================================
PART J — COST CONTROL
==================================================

NVIDIA latency is expensive.

Do this in stages.

STAGE 1
All 35 files:
offline ingestion/profile only.

STAGE 2
Select 6–8 representative datasets.

STAGE 3
Build deterministic gold questions.

STAGE 4
Run offline tests.

STAGE 5
Run only 2 smoke questions per selected dataset.

If 8 datasets:
maximum ~16 smoke questions.

Then STOP and report.

Do NOT immediately run the full 25–40 question NVIDIA suite.

I want to inspect the smoke-test results first.

==================================================
PART K — WHAT I WANT FROM YOU NEXT
==================================================

Proceed with:

1. All-35-file ingestion matrix.
2. Generic --pid/evaluator support.
3. Generic SignalLineFunction support.
4. Dataset profiling.
5. Select 6–8 representative files.
6. Propose 4–6 questions per selected file.
7. Derive deterministic expected facts.
8. Run offline tests.
9. Run MAXIMUM 2 live smoke questions per selected dataset.

Then report:

- total official files tested
- total successfully loaded
- warnings/failures
- exact selected 6–8 datasets
- why each dataset was selected
- files/code changed
- test count
- whether any dataset-specific code exists
- SignalLineFunction before/after
- smoke-test results per dataset
- unsupported claims
- estimated NVIDIA calls for full evaluation
- estimated runtime
- recommendation on whether to proceed with full 25–40 question cross-P&ID evaluation

STOP THERE.

Do not:
- run full evaluation
- email Sachin
- push final documentation
- change model
- optimize latency
- add OCR
- add unrelated features

until I approve the smoke-test report.
