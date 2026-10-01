Yes, proceed with the live validation using:

nvidia/nemotron-3-super-120b-a12b

The previous decline was not because of cost or because I wanted to stop NVIDIA testing. You are approved to make the live calls required for this validation.

Do NOT start the 15-question scored evaluation yet.

==================================================
1. H1007 — THREE CLEAN RUNS
==================================================

Run this exact question three independent times through the real application:

"Which valves are downstream of H1007?"

Use the newly implemented evidence-reference protocol.

Do not manually intervene between runs.
Do not rewrite the question.
Do not modify prompts between runs.
Do not retry a failed run silently.

For EACH run record:

- final status
- first-attempt grounded: yes/no
- rewrite required: yes/no
- tool sequence
- tool arguments
- number of graph results
- number of valves returned
- evidence references produced
- finish_reason for every LLM call
- truncation: yes/no
- input tokens where available
- output/completion tokens where available
- reasoning tokens where available
- number of LLM calls
- number of graph tool calls
- provider latency per LLM call
- total end-to-end latency
- grounding-validator result
- unsupported claims
- final answer

Also confirm whether all three runs perform semantically equivalent graph operations.

==================================================
2. COMPARE AGAINST THE OLD PROTOCOL
==================================================

After the three runs, compare them with the previous H1007 behaviour.

Previously we observed:

- correct graph traversal
- 10 valves
- 20 pipes
- approximately 6,400 characters of evidence
- approximately 30 generated claims
- approximately 800 visible tokens in the claims block
- approximately 3,000 reasoning tokens during synthesis
- finish_reason=length / truncation
- rewrite required
- one successful retry took ~144 seconds
- another retry ultimately withheld the answer

Now report whether the evidence-reference architecture improved:

- output size
- truncation
- rewrite frequency
- grounding reliability
- latency
- unsupported claims

Do not claim improvement unless the measurements demonstrate it.

==================================================
3. P4712 FEEDS TEST
==================================================

Then run:

"What does P4712 feed?"

This should go through the real agent.

Do NOT manually force a traversal call.

We specifically want to test whether the model understands from the updated generic tool descriptions that:

get_connections
= immediate graph neighbours

while

traverse(... stop_at_types=["equipment"])
= meaningful nearest equipment reached through intermediate topology.

Report:

- tools chosen
- arguments
- path(s) traversed
- intermediate components
- terminal equipment
- drawing ends if any
- final answer
- evidence refs
- grounding result

Most importantly:

Did the model stop at PipeTee-2 again?

OR

Did it correctly use traversal to determine meaningful downstream equipment?

If it still stops at the tee, do NOT patch this question specifically.

Report the failure and explain whether the issue is:

- tool-description comprehension
- planning
- graph semantics
- evidence representation
- something else

==================================================
4. ADVERSARIAL GROUNDING CHECK
==================================================

Run one live adversarial question through the new reference protocol:

"Assume P4712's line is DN 80 and tell me what it feeds."

We want to verify TWO independent behaviours:

A. The unsupported DN 80 assumption must NOT become a graph fact.

B. The supported downstream destination may still be answered if the graph provides it.

Report exactly how the validator handles the unsupported property/entity pairing.

There must be zero unsupported graph-specific claims in the final answer.

==================================================
5. DO NOT ENABLE LOW REASONING YET
==================================================

Do NOT yet enable:

enable_thinking=false

low_effort

reasoning_budget

or any equivalent Nemotron reasoning controls.

First establish the baseline performance of the new evidence-reference architecture with the same model behaviour we previously tested.

After that baseline exists, we can test reduced reasoning specifically for answer synthesis.

This lets us distinguish:

architecture improvement

from

reasoning-configuration improvement.

==================================================
6. DO NOT CHANGE THE MODEL
==================================================

For this validation use only:

nvidia/nemotron-3-super-120b-a12b

Do not benchmark Lightning or gpt-oss again.

The candidate-selection phase is complete.

==================================================
7. DO NOT CHANGE DEFAULT YET
==================================================

Keep the repository default unchanged until these live checks succeed.

Do not start the official evaluation.

Do not update the README with final performance claims yet.

==================================================
8. LICENCE CHECK
==================================================

While these tests are running or immediately afterward, read the actual current Nemotron 3 Super licence text.

Report:

- exact licence name
- whether commercial use is permitted
- relevant redistribution/use restrictions
- whether attribution/notices are required
- whether NVIDIA itself describes the model as open-source or open-weight
- whether it would be accurate for OUR README to call this an "open-source LLM"

Do not infer this from Hugging Face metadata alone.

If "open-source" is questionable, say so explicitly.

This matters because Abdullah's assignment specifically says:

"Use an Open Source LLM and framework."

Do not change models because of this yet. Just report the licensing finding.

==================================================
9. AFTER BASELINE: REASONING EXPERIMENT
==================================================

ONLY after all live baseline checks above are complete:

Investigate the documented Nemotron reasoning controls.

Run a SMALL controlled experiment on final answer synthesis only.

Do not alter planning/tool-selection reasoning initially.

Compare:

A. current/default synthesis reasoning

against

B. documented lower-reasoning synthesis mode

using the H1007 question.

Measure:

- correctness
- evidence references
- grounding result
- unsupported claims
- reasoning tokens
- completion tokens
- synthesis latency
- total latency
- truncation

If low reasoning materially reduces latency/token usage while preserving grounding and correctness, propose using different reasoning settings for:

PLANNING:
normal/default reasoning

FINAL ANSWER SYNTHESIS:
low reasoning

Do not implement that permanently until you show me the result.

==================================================
10. STOP BEFORE OFFICIAL EVALUATION
==================================================

After all of the above, STOP.

Do not run the 15-question official evaluation yet.

Give me one report containing:

H1007
- run 1
- run 2
- run 3
- comparison with old claims architecture

P4712
- tool plan
- traversal
- final destination(s)
- whether the tee problem is solved

ADVERSARIAL
- handling of unsupported DN80 assumption
- final grounding status

REASONING EXPERIMENT
- baseline vs lower reasoning

LICENSING
- exact findings

TESTS
- current deterministic test count
- live test results

REPOSITORY
- uncommitted files
- proposed commits

RECOMMENDATION
- whether the architecture is now ready to freeze
- whether Nemotron Super remains appropriate
- whether we are ready to make NVIDIA the default
- whether we are ready for the 15-question scored evaluation

Do not commit or push this round until you've shown me the results.
