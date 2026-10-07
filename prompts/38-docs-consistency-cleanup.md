Final documentation consistency cleanup only.

Do NOT change:
- source code
- tests
- prompts used for the agent
- evaluator
- gold
- evaluation artifacts
- holdout artifacts
- README metrics
- model configuration

Do NOT run NVIDIA.
Do NOT rerun any evaluation.

Audit the current documentation against the current main branch and fix only statements that
are now factually stale because of the cross-P&ID and follow-up work.

At minimum inspect:

- docs/HOW_IT_WORKS.md
- docs/DEMO_SCRIPT.md
- docs/ARCHITECTURE_DEEP_DIVE.md / similarly named architecture docs
- docs/SUBMISSION_AUDIT.md

Specific known stale statements to correct:

1. Any statement that says or implies only C01 / one drawing has been tested.
   Current accurate distinction:
   - all 35 official DEXPI 1.3 examples pass deterministic ingestion
   - eight structurally diverse additional P&IDs received live reasoning evaluation
   - the complex/rephrasing follow-up itself is on C01

2. Any statement saying there are only seven generic graph operations if presented as the
   current architecture.
   Clarify:
   - original agent exposed seven base graph tools
   - the follow-up added generic multi-step graph analyses for isolation boundaries,
     instrumentation chains, line tracing and route/reachability analysis

3. Remove any statement that says there is no multi-hop instrumentation tool.
   `trace_instrumentation` now exists.

4. Correct interview-prep sections that list old limitations such as:
   - "only one drawing has been tried"
   - "instrumentation chains cost one call per hop"
   where those statements no longer describe current main.

5. Do not erase history.
   If an old statement describes the original C01 evaluated build, label it explicitly as
   historical rather than rewriting history.

6. Keep the current limitations honest:
   - planner/tool-selection variance
   - incomplete/early traversal
   - retrieved facts sometimes omitted
   - directional vs direction-agnostic route semantics
   - paraphrase consistency is still weak
   - Nemotron is open-weight, not OSI-open-source

7. Do not improve or soften any evaluation number.

After edits:
- run no model inference
- run the deterministic docs/link/test checks only if already available
- commit as one docs-only commit:
  docs: align supporting docs with follow-up architecture

Report:
- exact stale statements fixed
- files changed
- test count if tests were run
- commit hash
- working tree status
- confirmation no evaluation artifact changed

Then STOP.
