# Submission audit

Each explicit requirement of the assignment ([prompts/00-original-assignment.md](../prompts/00-original-assignment.md)),
checked against the repository.

**Result: no blockers.** One important gap (no complete evaluation on the open-weight model)
and a few optional items are listed at the end.

## Data and task

| Requirement | Status | Where implemented | How to verify | Known limitation |
|---|---|---|---|---|
| Use pyDEXPI and its reference P&ID C01 | Met | `data/C01V04-VER.EX01.xml`; `ingestion/dexpi_loader.py` → `load_plant` | `uv run pid-agent inspect` prints plant 214 nodes / 376 edges, conceptual 36 / 39 | Only C01 has been run |
| Build on the pyDEXPI graph (`ProteusSerializer` → `GraphLoader` / `GraphAbstractor`) | Met | The three calls in `load_plant` | Read the function (70-line file); `tests/test_ingestion.py` | None |
| No hand-written stand-in dataset | Met | Every entity and connection is derived in `graph/normalizer.py` from the two pyDEXPI graphs | `tests/test_normalizer.py` checks edge attributes against plant segments for all 27 piping edges | Tests freeze some C01 values as expected results; that is test data, not the dataset |
| Explain how the graph is abstracted or indexed | Met | README "Design note"; `docs/HOW_IT_WORKS.md` "The two graphs" | Read them | None |
| Agent answers natural-language questions as a multi-step workflow | Met | `agent/workflow.py` → `PidAgent` (LangGraph) | `uv run pid-agent "<question>"` | Model may make redundant calls |
| Phase 1: find entities by tag, type or description | Met | `graph/entity_resolver.py`; tool `find_entities` | `uv run pid-agent tool find_entities '{"query": "tubular heat exchanger"}'` | Type-phrase matching uses a small stop-word list |
| Phase 2: neighbours, pipes between, paths, properties | Met | `get_connections`, `traverse`, `find_path`, `get_properties` in `graph/service.py` | `uv run pid-agent tool find_path '{"source_entity_id": "P4711", "target_entity_id": "H1007"}'` | `find_path` returns only the shortest route |
| Generalises: no mapping of known phrasings to fixed tool calls, in code or prompt | Met | Seven generic tools; `agent/prompts.py` has no entity names or recipes | `tests/test_agent.py::test_prompt_and_tool_specs_contain_no_assignment_examples_or_secrets`; `grep -rn "P4711" src/pid_agent/agent src/pid_agent/graph` finds one docstring example and no logic | The UI's example cards contain the sample questions; they are button labels only and are not sent to the model unless clicked |

## Requirements

| Requirement | Status | Where implemented | How to verify | Known limitation |
|---|---|---|---|---|
| Workflow visible: tool calls and what they returned, plus the answer | Met | CLI: `format_transcript` in `agent/workflow.py`. UI: "Tool calls", "Graph evidence", "Grounding" sections in `ui/app.py` | Run any question in the CLI or `uv run pid-agent-ui` | The trace shows operations, not model reasoning (by design) |
| Answers grounded in the graph | Met, with stated limits | `agent/grounding.py` → `check_grounding`; one regeneration; evidence-only fallback | `tests/test_grounding.py`; evaluation transcripts for questions 1 and 10 show rejected drafts | Lexical check: a wrong sentence built only from real values can pass; general-knowledge glosses are not detectable |
| Say so when the data does not contain something | Met | `missing` in `get_properties`; `not_found` in resolution; `open_end` connections | Evaluation questions 11 (weight), 14 (nonexistent valve), 15 (false premise) | None known |
| Open-source LLM | Partly demonstrated | Default: `openai/gpt-oss-20b` (open-weight) on Groq | README "Which model was actually used" | The only complete evaluation run is on DeepSeek `deepseek-chat`, a hosted alias whose weights and licence I have not verified. On `gpt-oss-20b` one evaluation question was answered before the provider's free daily quota ran out |
| Open-source framework | Met | LangGraph for the agent; pyDEXPI and NetworkX for the graph | `pyproject.toml` | pyDEXPI is AGPL-3.0 |
| Tell us which key is needed | Met | README "Configuration"; `.env.example` | Read them | `GROQ_API_KEY` by default; DeepSeek uses `DEEP_SEEK_API_KEY` |
| Setup simple: clone, install, run, one command each | Met | `git clone`, `uv sync`, `uv run pid-agent "<question>"` | Checked from a fresh clone (see below) | Needs `uv` installed and a key in `.env` (one `cp` plus editing) |

## Timebox and AI tools

| Requirement | Status | Where implemented | How to verify | Known limitation |
|---|---|---|---|---|
| Say roughly how long it took | Met | README "Time spent": approximately 5 to 6 hours hands-on | Read it | This is the author's own estimate. It cannot be derived from commit timestamps |
| Working core plus an honest list of what is missing | Met | README "Limitations" | Read it | None |
| Keep real commit history, not squashed | Met | `git log` (conventional commits per milestone) | `git log --oneline` | Git was started partway through, so the first two milestones were committed back to back when committing began. Nothing was squashed, amended or rewritten afterwards |
| Optionally include prompts or specs | Met | `prompts/00` to `prompts/14`, with an index | `prompts/README.md` | One early instruction (`04`) was not saved and is marked unavailable |

## What to send

| Requirement | Status | Where implemented | How to verify | Known limitation |
|---|---|---|---|---|
| GitHub repo link | **Not done yet** | No remote is configured; nothing has been pushed | `git remote -v` is empty | To do at submission time |
| The code | Met | `src/pid_agent/` | n/a | None |
| README: how to run | Met | README "How to run" | Follow it | None |
| README: design note under a page (abstraction, planning and traversal, why) | Met | README "Design note": about 580 words and one diagram | Read it | At the upper end of "under a page" |
| README: 5 to 10 transcripts, at least two failing or struggling | Met | README "Example transcripts": 9, of which 2 struggles and 3 failures; full files linked | Open the linked transcript files | The three failures are from development builds and are labelled with their commit |
| Eval: 10 to 20 questions with expected answers | Met | `evals/questions.json`: 15 questions, 41 required facts | `tests/test_eval.py` re-derives the facts from the graph | Questions written by the author |
| Eval: a script that scores them | Met | `evals/evaluator.py` (deterministic, no LLM judge) | `uv run python evals/evaluator.py` re-scores saved runs without a key | Checks presence of required facts, not everything else in the answer |
| Eval: the score | Met | README "Evaluation": DeepSeek `deepseek-chat` 15 of 15, mean 1.00 | Same command | One run; no score claimed for `gpt-oss-20b` |
| Eval set frozen before the run | Met | Questions and scorer in commit `407d6ba`; `run.json` records that commit | `git log -1 407d6ba`; `"commit"` in `evals/runs/deepseek-deepseek-chat/run.json` | None |
| Bonus: hosted link | **Not implemented** | n/a | n/a | The chat UI runs locally only |

## How they evaluate

| Criterion | Evidence |
|---|---|
| Works on questions it was not designed for | Generic tools; the evaluation questions differ from the examples and from development questions. Not proven beyond those |
| Uses the real graph and handles its messiness | Open ends recovered and marked; chamber-aware traversal; untagged valves found through derived identifiers; ambiguity returned, not guessed |
| Clean design, clear responsibilities | Layers: ingestion → normalizer → resolver/traversal → service → tools → agent → grounding. The UI and CLI are presentation only |
| Honest about limits; the eval measures something real | README "Limitations" and "How much to read into this" |
| Judgement about what to build | No vector store, no OCR, no hosting. The UI is a thin layer added last |

## Changes made after the evaluation

The evaluation ran against the agent at commit `a8d56b3`. Since then:

- No existing file under `src/pid_agent/` has changed (`git diff a8d56b3 -- src` shows only the new `ui/` package).
- The chat UI, its tests, and the documents under `docs/` were added. None of this was part of the 15-question run, and the evaluation was not re-run.
- The UI shows no confidence score, because the agent does not compute one.

## Findings

**Blockers** (violate an explicit requirement): none in the repository. The repository still has to be pushed to GitHub and the link sent.

**Important** (not required, but affects how the submission reads):

1. *No complete evaluation on the open-weight model.* The assignment asks for an open-source LLM. `openai/gpt-oss-20b` is the default and works, but the reported score is from `deepseek-chat`. Completing the run needs only a Groq key with quota: `LLM_PROVIDER=groq uv run python evals/evaluator.py --run` asks just the unanswered questions.
2. *The grounding check is lexical.* Documented, not fixed.

**Optional** (not built, on purpose): hosting; conversation memory between questions; multi-hop instrumentation traversal in one call; a second DEXPI file; highlighting on the drawing.

## Fresh-clone check

Run from a new clone of this repository, without an API key:

| Command | Result |
|---|---|
| `uv sync` | installs |
| `uv run pid-agent tool find_entities '{"query": "P4711"}'` | returns `CentrifugalPump-1` |
| `uv run pytest` | 440 passed, 4 deselected |
| `uv run python evals/evaluator.py` | re-scores both saved runs |
| `uv run pid-agent-ui` | page loads and shows the graph |
| `uv run pid-agent "..."` without a key | one-line error naming the variable to set |

Asking a question needs a provider key and was not repeated for this audit; the saved runs are the record of that.
