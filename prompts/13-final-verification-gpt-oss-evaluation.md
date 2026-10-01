We are at final verification. Do not modify the agent implementation.

Frozen production implementation:
a8d56b312e831d7ace33a267f251a9171e62f1d1

Current formal DeepSeek evaluation:
15/15 correct
41/41 required facts
commit containing evaluation definition before run: 407d6ba
documentation/results commit: 5e00f21

The remaining material requirement risk is the assignment's Open Source LLM
requirement.

Groq openai/gpt-oss-20b returned HTTP 200 in the most recent capacity check.

Proceed as follows.

1. PRESERVE DEEPSEEK RESULTS

Before running anything, preserve the existing DeepSeek evaluation artifacts
under clearly provider-specific filenames/directories.

The existing DeepSeek run must remain reproducible and must not be erased or
silently replaced.

Do not alter:
- evaluation questions
- expected facts
- scorer semantics
- production agent
- prompts
- graph implementation
- grounding
- traversal

If changing the evaluator output destination is necessary to prevent
overwriting the DeepSeek run, make the smallest evaluation-infrastructure-only
change necessary.

Do not touch src/.

2. VERIFY THE EVALUATION IS FROZEN

Confirm that the exact 15 questions and expected facts used for DeepSeek are
the ones that will be used for GPT-OSS.

Do not add, remove, rewrite, reorder or replace questions after seeing GPT-OSS
results.

Do not change expected facts.

Do not change scoring.

3. RUN GPT-OSS

Use:

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

Run the exact frozen 15-question evaluation once.

No semantic retries.
No tuning between questions.
No implementation changes.
No prompt changes.
No scorer changes.
No gold-answer changes.

Normal retry behaviour already implemented for transient provider rate limits
may remain unchanged.

If Groq's quota prevents completion, preserve all completed results and report
the remaining items as infrastructure blocked.

Do not switch to DeepSeek to fill missing GPT-OSS results.

4. CAPTURE RESULTS

For each question retain:

- exact question
- expected facts
- final answer
- visible workflow/tool trace
- model calls
- tool calls
- prompt tokens
- completion tokens
- total tokens
- latency
- grounding result
- regeneration
- fallback
- unsupported claims
- factual score
- outcome

5. SCORE WITH THE EXISTING DETERMINISTIC SCORER

Do not manually improve the score.

Do not use an LLM judge.

Report:

- mean score
- required facts found / total
- forbidden facts found
- correct
- partially correct
- incorrect
- abstained
- infrastructure failures
- model calls
- tool calls
- token usage
- regenerations
- fallbacks
- turn-limit hits

6. COMPARE PROVIDERS DESCRIPTIVELY

After the run, report DeepSeek and GPT-OSS side by side.

Do not rank them as "better" merely from one run.

Compare factual score, calls, token usage, grounding regenerations, fallbacks
and observed failure modes.

7. README

If the GPT-OSS evaluation completes, update the README so the primary
assignment-facing evaluation clearly identifies:

Provider: Groq
Model: openai/gpt-oss-20b

Include its actual score.

Keep the DeepSeek result as an additional frozen evaluation and identify it
accurately:

Provider: DeepSeek
Model: deepseek-chat

Do not claim anything about licensing that is not verified.

State only the exact model identifier and provider actually used.

If the GPT-OSS run is infrastructure-blocked, do not invent a score. Preserve
the DeepSeek evaluation and document the provider limitation honestly.

8. TIME SPENT

Do NOT infer engineering time from Git timestamps.

Leave the current time-spent value unchanged for now if changing it requires
guessing.

Flag it for Shaaz to provide the actual approximate hands-on time.

9. TEST

After any evaluation/docs-only changes:

run the complete deterministic test suite.

Run the saved-run scorer for both provider results where available.

Perform the secret scan.

10. GIT

No source-code modifications.

No squashing.
No rebasing.
No history rewriting.
No pushing.

Use existing Git identity.

Keep .env untracked.

No credentials in evaluation artifacts, transcripts, README, prompts or Git.

Create only a meaningful final evaluation/documentation commit if files
actually changed.

11. RETURN

FINAL VERIFICATION REPORT

A. PRODUCTION FREEZE
- frozen implementation hash
- confirmation src/ unchanged

B. DEEPSEEK EVALUATION
- score
- facts
- calls
- tokens
- grounding/regeneration/fallback

C. GPT-OSS EVALUATION
- completion status
- score
- facts
- calls
- tokens
- grounding/regeneration/fallback
- provider failures if any

D. PROVIDER COMPARISON

E. README STATUS

F. TEST STATUS

G. SECRET SCAN

H. COMMITS

I. GIT STATUS

J. REMAINING SUBMISSION RISKS

K. TIME-SPENT FIELD
- show the exact current README wording
- ask for the real approximate hands-on time

L. SUBMISSION READINESS

Then STOP.

Do not push.
