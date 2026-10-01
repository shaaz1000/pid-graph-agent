# Live smoke test of claim-level grounding

Seven questions asked once each against a live model after claim-level grounding was added.
This is not an evaluation and has no score. It only shows whether a real model can use the
structured-claims format. The agent was at commit `794a337`; four general fixes that this run
exposed were made afterwards (see the repository README).

| File | Provider and model | Outcome |
|---|---|---|
| `groq-gpt-oss-20b-01.txt` | Groq `openai/gpt-oss-20b` | Grounded: 2 claims, both supported |
| `groq-gpt-oss-20b-02.txt` | Groq `openai/gpt-oss-20b` | Withheld: the draft claimed a direct connection that does not exist; the one rewrite came back empty |
| `groq-gpt-oss-20b-03.txt` | Groq `openai/gpt-oss-20b` | Not answered: provider daily token quota (HTTP 429). Questions 4 to 7 were not asked on Groq |
| `deepseek-chat-03.txt` | DeepSeek `deepseek-chat` (diagnostic) | Limited: the model wrote its claims as one JSON array per line, which the parser did not accept at the time |
| `deepseek-chat-04.txt` | DeepSeek `deepseek-chat` (diagnostic) | Ambiguous: reported the five candidates, selected none |
| `deepseek-chat-05.txt` | DeepSeek `deepseek-chat` (diagnostic) | Grounded: 6 claims |
| `deepseek-chat-06.txt` | DeepSeek `deepseek-chat` (diagnostic) | Grounded after one rewrite: 5 claims; the false premise was corrected |
| `deepseek-chat-07.txt` | DeepSeek `deepseek-chat` (diagnostic) | Grounded after one rewrite: 21 claims |

The DeepSeek runs are a diagnostic substitute for the questions Groq's quota blocked. They
are not results for the open-weight model.
