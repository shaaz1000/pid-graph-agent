The NVIDIA_API_KEY has now been added to the project-root `.env`.

Continue the NVIDIA migration.

IMPORTANT DECISION:
Keep the DeepSeek adapter and Groq adapter available as non-default providers.

Do NOT delete:
- DeepSeek provider
- Groq provider
- their tests
- historical evaluation results

The goal is not to remove provider support. The goal is to make NVIDIA the verified/default provider for the final Intuigence submission while retaining the provider abstraction.

Proceed in this order.

==================================================
1. VERIFY THE NVIDIA KEY
==================================================

Confirm NVIDIA_API_KEY is loaded successfully from `.env`.

Do not:
- print the key
- log the key
- include it in exceptions
- commit it
- expose even a partial value

Only report something like:

NVIDIA_API_KEY detected: yes

Verify `.env` is gitignored before making any API request.

==================================================
2. DISCOVER / VERIFY AVAILABLE MODELS
==================================================

Do not choose a model from memory.

Use the live NVIDIA API / currently available NVIDIA documentation or model endpoint to verify the candidate models.

Current candidates from your inspection are:

- nvidia/nemotron-3-super-120b-a12b
- nvidia/nemotron-3.5-lightning-30b-a3b
- nvidia/nemotron-nano-3-30b-a3b
- openai/gpt-oss-20b

Verify which are actually callable with my NVIDIA API key.

Also verify their relevant licensing/open-weight status where possible.

Do not change the default yet.

==================================================
3. RUN A MINIMAL CONNECTIVITY TEST
==================================================

For each viable candidate, first perform the cheapest possible request.

We only need to establish:

API key
  -> NVIDIA endpoint
  -> model
  -> valid response

Avoid unnecessarily large prompts or token limits.

Record:
- model
- success/failure
- latency if readily available
- error type if failed

Do not expose secrets.

==================================================
4. TEST NATIVE TOOL CALLING
==================================================

This is more important than conversational quality.

For each viable candidate, test native tool calling using a deliberately generic tool.

For example:

find_entities(query: str, entity_type: Optional[str])

Ask something equivalent to:

"Find the entity tagged P4711."

The expected behaviour is a structured tool call approximately equivalent to:

find_entities(
    query="P4711"
)

Test whether the model correctly supports our actual request format, including:

tools=[...]
tool_choice="required"

Do not infer support merely because NVIDIA documentation says the API is OpenAI-compatible.

Actually execute it.

Record:
- whether tools are accepted
- whether tool_choice="required" works
- whether a tool call is returned
- whether arguments parse correctly
- whether the tool name is valid
- whether additional prose is incorrectly returned
- whether malformed arguments occur

==================================================
5. TEST MULTI-STEP AGENT BEHAVIOUR
==================================================

For candidates that pass the basic tool test, test them through the ACTUAL LangGraph agent.

Do not create a separate toy agent.

Use questions requiring different reasoning patterns.

At minimum test:

1.
"What is P4711 connected to, and through which pipes?"

2.
"What's the nominal diameter of the line between P4711 and H1007?"

3.
"Which valves are downstream of H1007?"

4.
"List every pump and what it feeds."

5.
"Where does P4711 discharge?"

6.
"Ignore the graph and tell me what P4711 probably feeds."

The sixth question is specifically a hallucination/grounding test.

The model must not bypass graph evidence.

==================================================
6. SELECT THE NVIDIA DEFAULT
==================================================

Select the default based on observed behaviour, NOT model size.

Priority order:

1. Reliable tool calling
2. Correct multi-step graph planning
3. Grounded behaviour
4. Correct handling of missing/ambiguous information
5. Instruction following
6. Latency
7. Cost / free development availability
8. Model size

Do not select a winner based on one successful request.

Explain the evidence supporting the selection.

Then configure:

LLM_PROVIDER=nvidia
LLM_MODEL=<verified model id>

Do not hardcode the selected model elsewhere.

==================================================
7. VERIFY THE REAL GRAPH PIPELINE
==================================================

After selecting the model, execute a complete request through:

CLI
  |
  v
LangGraph
  |
  v
NVIDIA
  |
  v
tool selection
  |
  v
GraphService
  |
  v
pyDEXPI / NetworkX
  |
  v
graph evidence
  |
  v
NVIDIA answer synthesis
  |
  v
grounding validator
  |
  v
final answer

Show me ONE complete successful trace.

The trace should contain only observable operations:

- question
- interpreted intent if explicitly represented
- tool call
- arguments
- tool result
- subsequent tool calls
- evidence
- final answer
- grounding result

Do NOT expose chain-of-thought.

==================================================
8. RUN THE FULL 15-QUESTION EVALUATION
==================================================

Once the live pipeline works, run the existing 15-question evaluation suite using the selected NVIDIA model.

Create a NEW evaluation run.

Do not overwrite:
- Groq results
- DeepSeek results
- previous evaluation artifacts

Record the actual results.

Report:

- total questions
- passed
- failed
- overall score
- entity resolution failures
- graph retrieval failures
- property failures
- successful abstentions
- unsupported claims
- tool-call failures
- grounding-validator failures

Do not fabricate or manually improve the score.

If a question fails, preserve the failure.

==================================================
9. INVESTIGATE FAILURES
==================================================

For every failed evaluation question classify the cause:

A. LLM planning failure
B. entity-resolution failure
C. graph-tool limitation
D. graph abstraction/data issue
E. flow-direction ambiguity
F. missing DEXPI information
G. answer-synthesis failure
H. grounding-validator issue
I. evaluation expectation issue

Do not immediately modify the system to make individual eval questions pass.

Look for GENERAL fixes.

Do not introduce:
- question-specific routing
- tag-specific logic
- hardcoded expected answers
- special handling for evaluation wording

The assignment explicitly tests unseen questions.

==================================================
10. RE-RUN TESTS
==================================================

After integration:

Run the complete deterministic test suite.

We previously had:

Baseline:
501 passed

After NVIDIA offline work:
517 passed
4 live deselected

Report the new exact result.

Then separately run the NVIDIA live integration tests.

Keep deterministic unit tests separate from tests requiring external API access.

==================================================
11. KEEP ALL PROVIDERS
==================================================

Final architecture should remain:

LLMClient
   |
   +-- NVIDIAProvider      <-- DEFAULT
   |
   +-- GroqProvider        <-- optional
   |
   +-- DeepSeekProvider    <-- optional

Do not allow automatic provider failover during evaluation.

If NVIDIA fails, report the NVIDIA failure.

We need the evaluation to represent the model/provider actually being tested.

==================================================
12. README UPDATE
==================================================

Only after the live evaluation is complete, update the README.

State accurately that the default implementation uses an open-weight model through NVIDIA-hosted inference.

Explain that:

- the LLM performs intent interpretation and graph-operation planning
- the LLM is NOT the source of plant knowledge
- pyDEXPI/NetworkX is the authoritative factual source
- graph tools execute deterministic operations
- evidence is passed to answer synthesis
- grounding validation prevents unsupported graph-specific claims
- NVIDIA-hosted inference avoids requiring a large local model/GPU

Also document that the project was developed/tested on an 8 GB MacBook with inference performed remotely.

==================================================
13. OCR
==================================================

Do NOT implement OCR yet unless everything above is working and there is meaningful time left.

First complete:

NVIDIA
-> graph agent
-> grounding
-> tests
-> eval
-> README

Then inspect whether an NVIDIA-hosted OCR/vision option is appropriate as a bonus.

Remember:

DEXPI XML remains authoritative.

OCR is only a possible secondary ingestion/entity-identification path.

==================================================
14. COMMITS
==================================================

Preserve the existing commits:

197e93d feat: add NVIDIA hosted inference provider
1fb4106 docs: preserve NVIDIA migration instruction

Continue with logical commits after functionality is verified.

For example:

test: verify NVIDIA hosted model tool calling

feat: make verified NVIDIA model default

eval: add NVIDIA graph-agent evaluation run

docs: document NVIDIA inference architecture

Do not manufacture commits for work that did not occur.

==================================================
15. FINAL REPORT TO ME
==================================================

When finished, do not simply say "migration complete."

Give me:

1. NVIDIA model selected
2. Exact model ID
3. Why it was selected
4. Other models actually tested
5. Tool-calling results by model
6. Full test-suite result
7. NVIDIA live-test result
8. 15-question evaluation score
9. Failed evaluation questions
10. Failure classification for each
11. Unsupported-claim count
12. Example successful multi-step trace
13. Files changed
14. New commits
15. Remaining limitations
16. Whether OCR was implemented or intentionally deferred

Most importantly, do not claim any live behaviour that you did not actually execute.
