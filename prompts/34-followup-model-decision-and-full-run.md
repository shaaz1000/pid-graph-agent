Decision update:

Do NOT use any paid inference provider.

Cost constraint for this follow-up:
USD 0.

Use the existing NVIDIA-hosted:
nvidia/nemotron-3-super-120b-a12b

for the remaining follow-up evaluation.

Do NOT use:
- Groq pay-as-you-go
- OpenRouter paid inference
- any provider requiring payment or account upgrade

Reason:
- the existing NVIDIA endpoint is already available;
- Nemotron performed materially better than gpt-oss-20b on this workload;
- Groq's free gpt-oss-120b quota is insufficient for the required evaluation;
- this follow-up should not require paid infrastructure.

LICENSING:
Be precise.

Do NOT call Nemotron OSI open source.

Describe it as:
"an open-weight model released under the NVIDIA Nemotron Open Model License."

If documentation discusses the follow-up requirement, note that:
- the implementation uses an open-weight hosted model;
- provider/model selection is abstracted;
- no paid inference service was required for this evaluation.

Do not make stronger licensing claims.

Continue using the exact frozen follow-up architecture:
- structured request decomposition
- typed direct facts
- deterministic derived facts
- typed unknowns
- application-rendered answers
- no semantic prose-regex grounding on the follow-up path
- one structured final repair
- current evaluator/gold

Before full run:
1. run the deterministic test suite;
2. record test count;
3. commit current follow-up implementation;
4. push;
5. record exact evaluated SHA;
6. ensure working tree is clean.

Then run the full mandatory follow-up suite with Nemotron.

Do not:
- modify prompts after evaluation starts
- change gold
- rerun poor answers for a better result
- add question-specific routing
- switch models during the run
- use any paid provider
- email Sachin

Track actual NVIDIA model calls, tokens, latency and provider failures.

In the final report, add a brief infrastructure note:

"Evaluation was run using the existing NVIDIA-hosted Nemotron 3 Super endpoint. No paid inference service or provider upgrade was required."

STOP after completing and reporting the full evaluation.
