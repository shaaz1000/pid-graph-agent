# 00 — Original assignment

**AUTHORITATIVE ASSIGNMENT FROM INTUIGENCE AI**

The text between the markers is the assignment exactly as received. Everything else in
`prompts/` is our own direction of the implementation.

--- BEGIN ORIGINAL ASSIGNMENT ---

Hey Shaaz, it was great speaking with you today! As I mentioned, here's the take home project we'd want you to implement:

**Background**
We build AI engineers for oil & gas plants. Plants are described by P&IDs (piping and instrumentation diagrams). We turn these into knowledge graphs, and an agent answers engineers' questions over them. This exercise is a small version of that.

**The data**
Use pyDEXPI and its reference P&ID:

- pyDEXPI: https://github.com/process-intelligence-research/pyDEXPI
- Reference P&ID (C01): https://github.com/process-intelligence-research/pyDEXPI/blob/master/data/C01V04-VER.EX01.xml
- Graph loader: https://github.com/process-intelligence-research/pyDEXPI/blob/master/pydexpi/loaders/graph_loader.py

pyDEXPI already loads C01 into a NetworkX graph (`ProteusSerializer` → `GraphLoader` / `GraphAbstractor`; see "Graph export" in its README). Build on that graph. Don't hand-write a stand-in dataset. You choose how to abstract or index the graph, but explain the choice.

**The task**
Build an agent that answers natural-language questions about this P&ID as a multi-step workflow. A typical question has two phases:

1. Find the entities the question refers to, whether by tag, type, or description.
2. Traverse the graph from them: neighbours, the pipes between them, paths, and the properties of what it found.

Example questions:

- "What is P4711 connected to, and through which pipes?"
- "Which valves are downstream of the heat exchanger H1007?"
- "What's the nominal diameter of the line between P4711 and H1007?"
- "List every pump and what it feeds."

**These examples are illustrative, not the spec.** When we review, we'll run a set of questions you haven't seen, phrased in different ways. Solutions that map known phrasings to fixed tool calls, in code or in the prompt, won't generalise, and that is the main thing we test.

**Requirements**

- **The workflow must be visible.** For each question, show the steps the agent took (the tool calls and what they returned) as well as the final answer.
- **Answers must be grounded in the graph.** If the data doesn't contain something, say so. Don't make it up.
- **Use an Open Source LLM and framework.** A hosted API is fine. If your solution needs a key, tell us which one and we'll plug ours in.
- **Setup must be simple.** Clone, install, run a question: at most one command each.

**Timebox**
Plan on about 4–6 hours and send it back within 5 days. Tell us roughly how long you spent. We'd rather see a working core and an honest list of what's missing than something polished that took three times as long.

**AI tools**
Use them. This is how we work. We're interested in how you direct them, so keep your real commit history (don't squash it into one commit). If you like, include a few of the prompts or specs that shaped the design.

**What to send**
A link to a GitHub repo containing:

1. The code.
2. A README containing:
   - how to run it
   - a short design note (under a page): your graph abstraction, how the agent plans and traverses, and why
   - 5–10 example transcripts, including at least two where it fails or struggles
3. A small eval: 10–20 questions with expected answers, a script that scores them, and the score you got.
4. Bonus: If you have it hosted somewhere please send that link as well.

**How we'll evaluate**

- It works on questions it wasn't designed for.
- It uses the real graph and handles its messiness.
- The agent design is clean and each part has a clear responsibility.
- You're honest about the limits and the eval measures something real.
- You showed good judgement about what to build in the time you had.

If anything is blocking you, please email me.

Best,
Abdullah

--- END ORIGINAL ASSIGNMENT ---
