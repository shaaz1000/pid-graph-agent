Small configuration correction before running M2.2a.

My existing environment variable is intentionally named:

DEEP_SEEK_API_KEY

Do NOT rename the variable in my .env.

Instead, update the DeepSeek provider/configuration to use:

DEEP_SEEK_API_KEY

consistently.

This includes:

- runtime configuration
- .env.example
- relevant tests
- secret-scanning logic if necessary
- any provider-specific configuration documentation

Do NOT print, inspect, copy or expose the value of DEEP_SEEK_API_KEY.

The actual secret must remain only in .env.

For the DeepSeek diagnostic run use:

LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

Do not use deepseek-reasoner for this diagnostic.

Do not modify the graph layer, agent workflow, prompts, tools, grounding,
compaction, traversal or budgets as part of this configuration correction.

Save this instruction as the next sequential prompt-history file before
making changes.

Run the deterministic test suite after the variable-name correction.

The current baseline is:

363 passed
0 failed
4 live deselected

If everything passes, make one small truthful commit such as:

fix: align DeepSeek environment configuration

Do not amend e63a83b.
Do not push.

Then run the already-frozen 8-question DeepSeek diagnostic set exactly ONCE
using:

LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

The diagnostic questions are already fixed in scripts/live_smoke.py.

Do NOT modify them.

Do NOT modify implementation between questions.

Do NOT retry incorrect answers.

Do NOT tune after an individual question.

For every question capture:

- exact question
- provider
- model
- tool sequence
- tool-call count
- model-call count
- token usage
- latency
- final answer
- grounding result
- unsupported claims
- fallback usage
- outcome:
  correct
  partially_correct
  incorrect
  abstained
  infrastructure_failure

After all 8 questions, classify any failures by root cause:

PLANNING
TOOL_SEMANTICS
ENTITY_RESOLUTION
GRAPH_LIMITATION
COMPACTION
STATE_REUSE
ANSWER_SYNTHESIS
GROUNDING
PROVIDER_FORMATTING
MODEL_VARIANCE
INFRASTRUCTURE

IMPORTANT:

Do NOT fix failures yet.

I want to see the complete frozen 8-question DeepSeek result before deciding
whether any additional change is justified.

Do NOT run a second DeepSeek diagnostic round.

Do NOT probe Groq.

Do NOT start the five-question Groq verification.

Do NOT start M3.

Return:

1. configuration correction made
2. commit hash
3. deterministic test results
4. all 8 DeepSeek results in a compact table
5. complete details for any incorrect/partial answers
6. root-cause classification for failures
7. total/average model calls
8. total/average tool calls
9. total/average tokens
10. turn-limit hits
11. redundant lookup observations
12. whether Q5-style reachability worked
13. whether Q12-style instrumentation composition worked
14. whether property/grounding behavior worked
15. whether you see any BLOCKING GENERAL ARCHITECTURE ISSUE

Then STOP.

Do not make further changes until I review the results.
