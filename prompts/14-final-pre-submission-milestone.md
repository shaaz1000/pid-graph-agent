I want to change direction for the final milestone.

The architecture deep dive is technically comprehensive, but it is still too
difficult for me to understand quickly.

Do NOT make it longer.

I now want three things:

A. A SIMPLE VISUAL EXPLAINER THAT TEACHES ME THE SYSTEM
B. A POLISHED LOCAL CHATBOT UI SO I CAN USE THE AGENT MYSELF
C. A FINAL GAP AUDIT AGAINST ABDULLAH'S ORIGINAL ASSIGNMENT

This is the final pre-submission milestone.

============================================================
0. READ THE ORIGINAL ASSIGNMENT FIRST
============================================================

Before doing anything, read:

prompts/00-original-assignment.md

Treat Abdullah's original email as the source of truth.

Then inspect the current repository and current HEAD.

Do not assume more features are better.

For every proposed change ask:

"Does this help satisfy, demonstrate, understand or test something Abdullah
actually cares about?"

If not, do not build it.

============================================================
PART A — TEACH ME THE SYSTEM
============================================================

The current architecture deep dive is useful as a reference manual but it is
not working for me as a learning document.

Do NOT replace it.

Instead create:

docs/HOW_IT_WORKS.md

This document is specifically for someone who understands software/AI systems
but did not write this code.

Target reading time:

10–15 minutes.

Maximum target length:

approximately 500–700 lines, preferably less.

Use diagrams and concrete examples much more than long prose.

============================================================
1. START WITH ONE SCREEN
============================================================

The first screen should answer:

WHAT DID I BUILD?

WHY DOES IT EXIST?

HOW DOES ONE QUESTION GET ANSWERED?

Use plain engineering language.

Then show ONE diagram:

User
  |
  | "What is P4711 connected to?"
  v
Agent / LLM planner
  |
  | chooses graph operation
  v
Graph tool
  |
  v
pyDEXPI / NetworkX
  |
  | factual evidence
  v
Agent
  |
  | grounded wording
  v
Grounding check
  |
  v
Answer + evidence + trace

Use the actual implementation.

============================================================
2. EXPLAIN THE MOST IMPORTANT IDEA
============================================================

Make this impossible to misunderstand:

THE LLM DOES NOT KNOW THE PLANT.

The graph knows the plant.

The LLM's job is approximately:

- understand the question
- identify what graph operation is needed
- call the appropriate tool
- inspect results
- decide whether another operation is necessary
- phrase the supported result

The deterministic system's job is:

- load C01
- resolve entities
- traverse connections
- find paths
- retrieve properties
- produce evidence
- validate factual claims

Use a side-by-side table.

============================================================
3. WALK THROUGH ONE REAL QUESTION
============================================================

Use:

"What is P4711 connected to, and through which pipes?"

Walk through it visually.

Do NOT expose hidden chain-of-thought.

Show only observable system behavior.

For every step show:

USER
↓
AGENT ACTION
↓
TOOL CALL
↓
TOOL RESULT
↓
NEXT ACTION
↓
FINAL ANSWER
↓
GROUNDING

Use actual current tool output.

I want to understand exactly where each value in the final answer came from.

============================================================
4. THEN WALK THROUGH A MULTI-STEP QUESTION
============================================================

Pick one real saved evaluation example that requires multiple operations.

Explain:

why one tool call wasn't enough

what entity was resolved

what traversal/path operation happened

what evidence came back

how the answer was constructed

what grounding checked

Again: observable behavior only, no private chain-of-thought.

============================================================
5. EXPLAIN THE TWO GRAPHS LIKE I'M NEW TO THIS REPO
============================================================

Do not begin with implementation terminology.

Start with the problem.

Explain:

"Why can't I just use the pyDEXPI graph directly for everything?"

Then introduce:

PLANT GRAPH

and

CONCEPTUAL GRAPH

Use one concrete C01 example.

Show visually what information each contains.

Then explain why the application uses both.

I should be able to explain this to Abdullah afterward.

============================================================
6. EXPLAIN THE SEVEN TOOLS VISUALLY
============================================================

Create one simple table:

TOOL
WHAT I WOULD ASK IT
WHAT IT ACTUALLY DOES

Then use tiny diagrams for:

get_connections

A -- B

traverse

A -- B -- C -- D

find_path

A ===== route ===== D

Make adjacency vs reachability vs path extremely clear.

============================================================
7. EXPLAIN THE HEAT EXCHANGER PROBLEM SIMPLY
============================================================

This is an important engineering decision.

Show:

process side

utility side

and why:

process inlet
→ exchanger
→ utility outlet

would be a false graph path.

Then show how chamber-aware traversal prevents it.

Use the real implementation semantics.

============================================================
8. EXPLAIN OPEN ENDS
============================================================

Show one real example.

Explain:

what pyDEXPI conceptual abstraction lost

what was still available in the plant graph

what we recovered

what we deliberately DID NOT invent

Make the distinction between:

known open boundary

and

unknown destination

clear.

============================================================
9. EXPLAIN GROUNDING WITH A GOOD AND BAD ANSWER
============================================================

Use an actual historical example if available.

GOOD:

graph says DN80
answer says DN80
→ supported

BAD:

graph contains 800 mm somewhere / model interprets it as DN800
→ unsupported/wrong semantic role
→ rejected

Explain how the validator works at a conceptual level.

Then point me to the actual code.

============================================================
10. EXPLAIN FAILURE MODES
============================================================

Use a table:

PROBLEM
WHAT USER SEES
WHAT SYSTEM DOES

Include:

entity not found
ambiguous entity
property missing
no path
open end
truncated traversal
unsupported draft
provider failure

Keep it concrete.

============================================================
11. EXPLAIN THE AGENT LOOP
============================================================

Show the actual state machine visually:

plan
↓
execute tools
↓
plan again if needed
↓
draft
↓
validate
↓
regenerate if necessary
↓
final

Explain why this is an agent rather than a single LLM call.

============================================================
12. GIVE ME "HOW TO EXPLAIN THIS IN AN INTERVIEW"
============================================================

At the end create:

30 SECOND VERSION

2 MINUTE VERSION

5 MINUTE TECHNICAL VERSION

Use natural language I could actually say aloud.

Then answer:

Why graph instead of RAG?

Why NetworkX?

Why two graph representations?

Why use an LLM at all?

How do you prevent hallucinations?

What does downstream mean?

What happens with heat exchangers?

What happens when data is missing?

How did you evaluate it?

What are the biggest current limitations?

What would you build next in production?

============================================================
PART B — BUILD A LOCAL CHATBOT UI
============================================================

I want to SEE and USE the agent.

Build a lightweight local UI around the EXISTING agent.

The UI must NOT replace or duplicate agent logic.

It is only a presentation layer.

============================================================
13. TECHNOLOGY CHOICE
============================================================

First inspect the repository.

Choose the smallest reasonable local UI approach.

Streamlit is acceptable if it adds minimal complexity.

A lightweight existing Python UI framework is also acceptable.

Do NOT build:

React frontend
Node backend
database
authentication
deployment infrastructure

unless absolutely necessary, which it should not be.

Explain the chosen UI dependency before implementing.

============================================================
14. CHAT UI
============================================================

I want a clean modern chat interface.

Think:

technical engineering copilot

not consumer AI toy.

Layout:

LEFT SIDEBAR

P&ID Graph Agent

Loaded drawing:
C01V04-VER.EX01.xml

Provider:
<current provider>

Model:
<current model>

Graph:
Plant: <actual nodes/edges>
Conceptual: <actual nodes/edges>

Navigation / controls:
New conversation
Example questions
About the graph

MAIN AREA

Header:
P&ID Engineering Assistant

Subtext:
Ask questions about equipment, piping, connectivity,
instrumentation and properties in the loaded P&ID.

Then normal chat messages.

============================================================
15. EMPTY STATE
============================================================

Before a question is asked, show useful example cards.

Examples should be actual supported categories, such as:

Connectivity

"What is P4711 connected to?"

Traversal

"What is downstream of H1007?"

Properties

"What is the nominal diameter of the line between P4711 and H1007?"

Inventory

"List every pump."

Instrumentation

Use an actual valid instrumentation-style example.

Do not wire these examples into agent behavior.

They are only UI suggestions.

============================================================
16. ANSWER PRESENTATION
============================================================

For every response, separate:

ANSWER

from:

EVIDENCE / WORKFLOW

The normal answer should remain readable.

Under it provide expandable sections:

▸ How this answer was found

▸ Tool calls

▸ Graph evidence

▸ Grounding

▸ Warnings

Only show sections that contain data.

============================================================
17. TOOL CALL UX
============================================================

Make tool calls visually understandable.

For example:

Step 1
find_entities

Input:
query = "P4711"

Result:
CentrifugalPump-1
tag: P4711

Step 2
get_connections

Input:
entity = ...

Result:
...

Do not dump giant raw JSON by default.

Provide optional:

"View raw result"

inside an expander if practical.

============================================================
18. GROUNDING UX
============================================================

Make grounding visible but restrained.

For example:

Grounded against graph evidence ✓

If the current implementation exposes deterministic confidence after the
guardrail milestone, show it.

If confidence has NOT actually been implemented yet, do NOT fake it in UI.

Never ask the LLM to invent confidence.

============================================================
19. AMBIGUITY UX
============================================================

If the graph returns ambiguity:

show the possible matches clearly.

Do not make the UI pretend an answer exists.

If practical, allow the user to copy/select an identifier and ask again.

Do not build complicated stateful disambiguation unless already supported.

============================================================
20. MISSING DATA UX
============================================================

Clearly distinguish:

Entity not found

Property not present in graph

No represented path

Open graph boundary

Provider/API failure

Out-of-scope request, if scope guardrails exist

Do not turn all failures into red exception boxes.

Expected graph limitations are normal product states.

============================================================
21. VISUAL DESIGN
============================================================

Make the UI polished enough that I could screen-share it during an interview.

Use:

- generous spacing
- clear typography
- restrained palette
- cards
- subtle borders
- readable technical metadata
- responsive layout

Avoid:

- excessive gradients
- giant hero sections
- emojis everywhere
- animations
- fake metrics
- marketing language

Do not spend excessive time styling.

Functionality and transparency matter more.

============================================================
22. DO NOT HIDE THE WORKFLOW
============================================================

Abdullah explicitly requires:

"The workflow must be visible."

Therefore the UI must make the workflow easy to inspect.

A reviewer should be able to ask a question and immediately inspect:

what tools ran

what they returned

what evidence supported the answer

whether grounding accepted/rejected anything

============================================================
23. CONVERSATION BEHAVIOR
============================================================

Inspect whether the existing agent actually supports conversational context.

If it does:

use it correctly.

If it does not:

do NOT pretend it does.

Each submitted question may remain an independent agent run.

The UI can still display previous Q&A messages for convenience.

Document this distinction clearly.

============================================================
24. LOCAL RUN COMMAND
============================================================

I want ONE easy command.

Prefer something like:

uv run pid-agent-ui

or:

uv run streamlit run ...

Choose based on repository conventions.

The README should show the exact command.

Verify it.

============================================================
25. UI TESTING
============================================================

Do not rely only on visually opening the page.

Test the adapter between UI and agent.

At minimum:

successful answer

tool trace rendering

grounding rendering

ambiguity

not found

provider error

missing optional fields

Do not create a huge browser automation suite for a take-home.

============================================================
PART C — FINAL ASSIGNMENT GAP AUDIT
============================================================

After Parts A and B, STOP FEATURE DEVELOPMENT.

Read Abdullah's original assignment again.

Create:

docs/SUBMISSION_AUDIT.md

This should be concise.

Use a table:

REQUIREMENT
STATUS
WHERE IMPLEMENTED
HOW TO VERIFY
KNOWN LIMITATION

Audit EVERY explicit requirement from his email.

============================================================
26. PAY SPECIAL ATTENTION TO THESE
============================================================

Verify:

REAL DATA
Are we definitely loading the supplied C01 through pyDEXPI?

GENERALIZATION
Are tools generic or are known questions encoded?

VISIBLE WORKFLOW
Can both CLI and UI expose tool calls/results?

GROUNDING
Can unsupported facts escape?

OPEN SOURCE LLM
What exactly can we truthfully claim?

SETUP
Can someone clone/install/run with one command each?

README
Does it contain everything requested?

TRANSCRIPTS
Are there 5–10 including at least two struggles/failures?

EVALUATION
Are there 10–20 questions?
Expected answers?
Scoring script?
Reported score?
Frozen-before-run evidence?

TIMEBOX
Is the reported time truthful?

AI TOOLS
Is real commit history preserved?

LIMITATIONS
Are we explicit?

HOSTING
Clearly mark as bonus/not implemented if absent.

============================================================
27. FIND REAL BLOCKERS ONLY
============================================================

Classify anything missing as:

BLOCKER
violates an explicit assignment requirement

IMPORTANT
not explicitly required but materially improves reviewability

OPTIONAL
nice-to-have

Do not implement OPTIONAL items.

Do not automatically implement IMPORTANT items.

Report them.

If you find a BLOCKER, fix only the smallest necessary change.

============================================================
28. DO NOT RE-RUN FORMAL LLM EVALUATION
============================================================

Do not call Groq.

Do not call DeepSeek.

Do not modify saved formal evaluation artifacts.

Do not claim the new UI/guardrail work was part of the historical 15/15 run.

Historical evaluation must remain historically accurate.

============================================================
29. README FINAL UX
============================================================

After everything is complete, inspect README as a first-time reviewer.

The first part should quickly tell Abdullah:

what this is

how to install

how to ask a question

how to launch the optional local UI

where the evaluation is

where transcripts are

where architecture docs are

Keep the design note concise enough to respect his "< one page" request.

Do not turn README into a huge document.

============================================================
30. LOCAL DEMO SCRIPT FOR ME
============================================================

Create:

docs/DEMO_SCRIPT.md

I want to be able to open the UI and demo this project in approximately
5 minutes.

Give me:

QUESTION 1
simple entity/connectivity question

WHAT TO POINT OUT

QUESTION 2
multi-step traversal/path question

WHAT TO POINT OUT

QUESTION 3
missing/ambiguous/false-premise question

WHAT TO POINT OUT

QUESTION 4
instrumentation question

WHAT TO POINT OUT

QUESTION 5
one failure/limitation

WHAT TO POINT OUT

Then give me a 30-second closing explanation.

Use actual supported questions verified against the graph.

============================================================
31. FINAL VALIDATION
============================================================

Run all deterministic tests.

Run UI adapter tests.

Run saved evaluation scorer without provider calls.

Run secret scan.

Verify no API key appears in:

git history
source
docs
UI
logs
saved transcripts

Verify all run commands from a clean environment as far as practical.

Do not run formal live LLM evaluation.

============================================================
32. GIT
============================================================

Preserve existing history.

Do not amend.

Do not squash.

Do not push.

Do not add AI attribution.

Do not commit API keys.

Use logical commits.

Suggested:

docs: add simplified architecture walkthrough

feat: add local graph-agent chat interface

docs: add submission audit and demo guide

Only create a commit when there is meaningful content for it.

============================================================
33. REPORT BACK
============================================================

Return:

FINAL PRE-SUBMISSION MILESTONE

A. ORIGINAL ASSIGNMENT AUDIT BEFORE CHANGES

B. SIMPLE EXPLAINER
- file
- approximate reading time
- diagrams
- what it teaches

C. LOCAL CHATBOT
- framework
- files
- exact launch command
- screenshots if available
- how tool traces appear
- how grounding appears

D. REQUIREMENT AUDIT
- blockers
- important items
- optional items

E. DEMO
- exact command
- first five questions I should try

F. TESTS

G. SAVED EVALUATION VERIFICATION

H. SECRET SCAN

I. COMMITS

J. GIT STATUS

K. WHAT IS STILL MISSING BEFORE SUBMISSION

Then STOP.

Do not push.
