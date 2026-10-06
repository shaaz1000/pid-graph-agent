# Diagnostic smoke runs

Small runs (3 complex questions, 8 phrasings, one run each) made while the follow-up path was
being built. They are kept as a record of what each change did. They are not the evaluation:
the agent changed between them, so their numbers are not comparable with each other or with
`runs/`.

| Folder | Agent at that point | Models |
|---|---|---|
| `smoke-1-before-harness-fixes/` | First structured answers; a model summary was still shown | gpt-oss-20b (NVIDIA), Nemotron 3 Super (NVIDIA), gpt-oss-120b (Groq, 4 questions) |
| `smoke-2-after-harness-fixes/` | No model text in answers; tool-name cleaning; name resolution; evaluator fixes | gpt-oss-20b (NVIDIA) |
| `smoke-3-request-coverage/` | Request decomposition, coverage validation, one final repair | gpt-oss-120b (Groq). Stopped after 8 of 11 questions by the free tier's daily token limit |

Each folder holds `run.json` (full traces), the `report.json` written at the time, and transcripts.
