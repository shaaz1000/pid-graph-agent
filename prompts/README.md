# Prompt history

The instructions that shaped this project, in the order they were given. Files are kept as
written; later prompts never overwrite earlier ones.

| File | What it is | Status |
|---|---|---|
| `00-original-assignment.md` | The assignment from Intuigence AI | Exact text, as received |
| `01-implementation-spec.md` | Initial implementation specification | Preserved development instruction (exact file, previously `PROMPT.md`) |
| `02-deterministic-graph-layer.md` | Go-ahead and clarifications for the deterministic graph layer | Preserved development instruction (exact file, previously `ImplementationPrompt.md`) |
| `03-git-milestone-workflow.md` | Git milestone workflow and attribution rules | Preserved development instruction (exact file, previously `Git_Commit.md`) |
| `04-llm-agent-implementation.md` | LLM adapter and LangGraph agent instructions | **Original exact instruction unavailable** — placeholder only, not reconstructed |
| `05-agent-stabilization.md` | Agent stabilization and the prompt-history rule | Preserved development instruction |
| `06-pre-evaluation-provider-verification.md` | Prompt-history repair, second LLM provider, live verification | Preserved development instruction |
| `07-deepseek-diagnostic-verification.md` | Temporary diagnostic provider, diagnostic run rules, official verification procedure | Preserved development instruction |
| `08-deepseek-configuration-and-diagnostic-run.md` | Key-variable name correction and the frozen eight-question diagnostic run | Preserved development instruction |
| `09-final-stabilization-and-official-verification.md` | Two approved fixes after the diagnostic run, architecture freeze, official verification procedure | Preserved development instruction |
| `10-model-facing-hygiene-and-freeze.md` | Removal of dataset-specific examples from model-facing text; final freeze and verification rules | Preserved development instruction |
| `11-official-groq-verification-request.md` | Request to run the frozen five-question verification on the primary provider (superseded before it ran: quota) | Preserved development instruction |
| `12-formal-evaluation-and-documentation.md` | Formal 15-question evaluation, scoring, transcripts and README requirements | Preserved development instruction |
| `13-final-verification-gpt-oss-evaluation.md` | Preserve the first evaluation run and repeat the frozen evaluation on the open-weight model | Preserved development instruction |
| `14-final-pre-submission-milestone.md` | Short visual explainer, local chat UI over the existing agent, and a requirement audit against the assignment | Preserved development instruction |
| `15-structured-claim-grounding.md` | Post-publication hardening: claim-level structured grounding, typed evidence validation and focused guardrails | Preserved development instruction |
| `16-final-release-readiness.md` | Release audit, live smoke test of claim-level grounding, licensing, stale-document fixes, freeze | Preserved development instruction |
| `17-nvidia-provider-migration.md` | Switch the hosted LLM provider to NVIDIA's OpenAI-compatible API with an open-weight model | Preserved development instruction |
| `18-nvidia-verification-and-default.md` | Verify the NVIDIA key, probe candidate models for tool calling and agent behaviour, keep all adapters | Preserved development instruction |
| `19-claims-truncation-and-scaling-brief.md` | Timeout investigation outcome: treat claims-block truncation as a scaling issue, plan a general fix | Preserved development instruction |
| `20-evidence-reference-grounding.md` | Approve evidence references, relationship-aware validation, truncation detection, traversal semantics | Preserved development instruction |
| `21-live-validation-of-evidence-references.md` | Live validation runs on the selected model, licence check, reasoning experiment | Preserved development instruction |
| `22-finish-and-submit.md` | Stop expanding scope: application-side rendering of simple results, evaluation, documentation, commit and push | Preserved development instruction |
| `23-evaluation-baseline-instructions.md` | Let the evaluation finish untouched; what to capture and report as the baseline | Preserved development instruction |
| `24-freeze-and-submit.md` | Freeze the agent, accept the NVIDIA baseline, fix provenance for future runs, finish documentation, commit and push | Preserved development instruction |
| `25-cross-pid-generalization-request.md` | Reviewer follow-up: show the same architecture works on more DEXPI files; audit, dataset discovery and plan before any live runs | Preserved development instruction |
| `26-broad-and-deep-generalization-plan.md` | Ingest all 35 official DEXPI 1.3 files, generic dataset selection, SignalLineFunction fix, representative datasets with smoke tests | Preserved development instruction |
| `27-validator-fixes-and-cross-pid-evaluation.md` | Fix the four generic validator defects found by the smoke test, then one full 37-question cross-P&ID run | Preserved development instruction |
| `28-post-evaluation-hardening.md` | After the frozen evaluation: close the hedge-word and relation-synonym bypasses, stop token-free factual prose from counting as grounded, correct stale documentation | Preserved development instruction |

`00` is the requirement. `01` onward are our own instructions for building it.

History of this directory: it was created with `05`; `01`-`03` were moved in at that point,
and `00` held an "unavailable" placeholder until the assignment text was supplied with `06`.
