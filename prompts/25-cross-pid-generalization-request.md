Sachin from Intuigence AI reviewed the submission and gave us one specific follow-up:

"Can you please do it for more Dexpi Files (if not already done)?
A single file is not a strong indicator of performance.
You can find more dexpi files online."

This is now the highest-priority task.

Repository:
https://github.com/shaaz1000/pid-graph-agent

Current accepted baseline:
- C01 pyDEXPI reference P&ID
- NVIDIA Nemotron 3 Super
- 556 tests passing, 4 live deselected
- 15-question C01 evaluation
- 12/15 fully correct
- 13.42/15 weighted score / 0.894 mean
- 14 grounded, 1 limited
- 0 unsupported final claims
- architecture currently built around pyDEXPI -> NetworkX -> generic graph tools -> agent -> grounding validator

IMPORTANT:
Do not immediately start changing the architecture.

Sachin's concern is DATASET GENERALIZATION, not whether we can manually make the existing C01 demo work on additional known questions.

We need to demonstrate that the same agent architecture can ingest and reason over multiple real DEXPI P&IDs without file-specific logic.

PHASE 1: INSPECT THE CURRENT REPOSITORY

First inspect the entire current implementation and determine:

1. Where C01 is currently hardcoded or assumed.
2. Whether the graph loader already accepts arbitrary DEXPI XML paths.
3. Whether entity resolution has any C01-specific assumptions.
4. Whether graph abstraction has C01-specific assumptions.
5. Whether graph tools have tag/type/property assumptions that may fail on another DEXPI file.
6. Whether the CLI/UI can select another P&ID.
7. Whether the eval framework can run against multiple P&IDs.
8. Whether prompts contain examples that could bias the agent toward C01.
9. Whether any tests or expected behaviours are accidentally dataset-specific.

Give me this audit BEFORE making broad changes.

PHASE 2: FIND REAL ADDITIONAL DEXPI FILES

Search the existing pyDEXPI repository and its official/reference datasets first.

Then search other credible public DEXPI sources if necessary.

We need preferably 2-4 additional REAL DEXPI/Proteus XML P&IDs.

Prioritize:
1. files already shipped with pyDEXPI
2. official DEXPI examples/reference files
3. other publicly available DEXPI-compliant Proteus XML files

Do NOT:
- fabricate XML
- generate synthetic P&IDs
- copy C01 and rename it
- hand-write stand-in graph data
- silently modify external files to make our parser accept them

For every candidate report:
- source
- filename
- DEXPI/Proteus version if identifiable
- whether pyDEXPI ProteusSerializer loads it unchanged
- graph node/edge counts
- entity/type/tag counts
- whether GraphAbstractor succeeds
- notable structural differences from C01
- licence/source attribution requirements

Prefer files that differ meaningfully from C01.

PHASE 3: INGESTION GENERALIZATION

The application should support:

pid-agent --pid <path-or-dataset> "question"

or an equally simple generic mechanism.

The dataset must be selected through configuration/input, NOT through code branches such as:

if dataset == "C02":
    ...

There must be:
- no C01-specific graph logic
- no tag-specific routing
- no question-specific routing
- no expected-answer-specific behaviour

The same:
- loader
- graph abstraction
- entity resolver
- tools
- LangGraph workflow
- grounding validator

must operate across every supported P&ID.

If a new real file exposes a genuine generic parser/abstraction issue, classify it first and propose the smallest GENERAL fix.

Do not patch around individual files.

PHASE 4: DATASET PROFILING

Before spending NVIDIA calls, build a deterministic dataset profiler.

For each successfully loaded P&ID report things such as:

- equipment tags
- equipment types
- valve tags/types
- instrumentation tags/types
- piping systems / line identifiers
- available nominal diameters
- connected components
- graph node/edge counts
- tagged vs untagged entities
- drawing/off-page connectors
- properties actually present

Use this profile to construct valid evaluation questions.

We must NOT invent questions whose expected answers we guessed manually.

Expected answers should be derived/verified deterministically from the graph.

PHASE 5: CROSS-P&ID EVALUATION

Create a separate generalization evaluation.

Do NOT alter or overwrite the accepted C01 baseline.

Keep the original:
0.894 C01 run
completely intact.

For each additional P&ID, construct a SMALL but meaningful evaluation, approximately 5-10 questions depending on graph richness.

Questions should cover available categories such as:

- exact entity lookup
- paraphrased entity lookup
- direct connection
- multi-hop path
- upstream/downstream traversal
- equipment enumeration
- piping/line property lookup
- instrumentation/control relationship where available
- missing-data question
- adversarial unsupported assumption

Do not force categories that the P&ID does not contain.

CRITICAL:
Questions must use identifiers/entities actually discovered from each graph.

Expected answers must be generated or independently verified using deterministic graph operations, not copied from the LLM's response.

The LLM is the system under test.
It cannot generate its own ground truth.

PHASE 6: MEASURE GENERALIZATION

Report results separately for each P&ID.

For each dataset:

- number of questions
- fully correct
- partial
- incorrect
- weighted score
- grounded
- limited
- unsupported claims
- tool failures
- parser failures
- planning failures
- grounding failures
- median latency
- mean latency
- LLM calls
- graph tool calls

Then provide an aggregate CROSS-DATASET score.

Do not combine the original C01 baseline into a misleading single number unless clearly labelled.

Most important question:

Did the SAME architecture work on previously unseen DEXPI files without dataset-specific changes?

PHASE 7: FAILURE ANALYSIS

Classify failures as:

A LLM planning
B entity resolution
C graph retrieval
D graph abstraction / DEXPI variation
E direction semantics
F missing source data
G answer synthesis
H grounding validator
I evaluation expectation
J parser/schema compatibility

Preserve failures.

Do NOT optimize against individual evaluation questions.

If another P&ID breaks something, show me the failure before deciding whether to fix it.

PHASE 8: COST / TIME CONTROL

NVIDIA latency was the major bottleneck in the previous evaluation.

Do not immediately run dozens of live questions.

Sequence:

1. discover datasets
2. verify deterministic loading
3. profile graphs
4. run offline tests
5. show me candidate datasets and proposed eval questions
6. WAIT FOR APPROVAL
7. only then run NVIDIA generalization evaluation

For the initial live smoke test, use at most 2-3 representative questions per new P&ID.

Do NOT run a large NVIDIA evaluation until I approve it.

PHASE 9: DOCUMENTATION PLAN

Do not rewrite README yet.

After results exist, propose a small section such as:

"Cross-P&ID Generalization"

It should explain:
- additional datasets
- where they came from
- whether any code changes were necessary
- evaluation results by dataset
- failures/limitations

This is specifically intended to answer Sachin's concern that performance on a single file is not enough evidence.

IMPORTANT CONSTRAINTS

Do not:
- change the accepted C01 evaluation
- delete old evaluation artifacts
- hide failures
- introduce dataset-specific branches
- introduce tag-specific rules
- add OCR
- switch LLM providers
- benchmark more models
- optimize NVIDIA latency
- add unrelated features
- email Sachin
- commit/push broad changes yet

FIRST RESPONSE I WANT FROM YOU:

1. Current C01-specific assumptions found in the code.
2. Real additional DEXPI files discovered.
3. Which ones load successfully with current pyDEXPI pipeline WITHOUT modification.
4. Structural differences between those files and C01.
5. Any failures encountered.
6. The 2-4 datasets you recommend for the generalization test and why.
7. Proposed 5-10 evaluation questions per dataset, with deterministic source of expected answer.
8. Minimal code changes, if any, required to make dataset selection generic.
9. Estimated number of NVIDIA calls and approximate runtime for the eventual evaluation.

STOP THERE.

Do not run the full live evaluation, modify architecture substantially, commit, push, or email anyone until I approve the plan.
