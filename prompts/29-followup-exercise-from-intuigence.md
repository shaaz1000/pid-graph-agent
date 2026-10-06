# 29 — Follow-up exercise from Intuigence AI

**AUTHORITATIVE FOLLOW-UP FROM INTUIGENCE AI**

Received as reviewer feedback plus an attached document, `PID_agent_followup_exercise.pdf`
(3 pages). The PDF itself is not committed (its licence is not stated); the text between the
markers is its content as received. Everything after this file in `prompts/` is our own
direction of the follow-up work.

--- BEGIN REVIEWER FEEDBACK ---

I evaluated your current work. The questions seem quite simple, and I noticed extensive use of
regex, which isn't a good practice for this type of task.

To evaluate the work, we would like to see:
1. Getting more complex questions answered about the P&IDs.
2. Same question rephrased in a different manner, ensuring the answer remains consistent
   across each turn.

You can use the attached PDF document to get some idea.

--- END REVIEWER FEEDBACK ---

--- BEGIN FOLLOW-UP EXERCISE ---

# Follow-up exercise: complex and rephrased questions

P&ID graph agent take-home · same reference P&ID (C01V04-VER.EX01)

Thanks for your submission. The questions plant engineers actually ask us are rarely single
lookups. They are operational: how to isolate something, what happens if a pump trips or a
valve loses power, whether anything can be blocked in without relief, where a control loop
really acts. They also reach us in many different wordings. This follow-up builds on the agent
you already have, on the same C01 P&ID, and focuses on those two things.

## What we're testing

- **1. Complex questions.** Questions that need several steps over the graph: isolation
  boundaries and closure order, trip and fail-position impact, blocked-in equipment and relief
  paths, full control-loop mapping, inventories with attributes, line tracing with branches,
  upstream and downstream reach with recycle, parallel paths, and describing the process and
  its controls. Every step must be grounded in the drawing. Where the drawing is silent (an
  off-page destination, a missing valve, an unstated actuator type), the answer should say so
  instead of assuming.
- **2. Consistency under rephrasing.** The same question asked in different words, each time
  as a separate turn, must produce the same facts. The wording will change: tag vs. type vs.
  property, abbreviations (PIC, CCR, DN), operator shorthand, terse fragments, items referred
  to by type or by a property ("the 84 kW pump") instead of tag. The entities and values in the
  answer must not. We will also ask the same question about different items.

*The examples below show the kinds of questions we mean. They are examples, not the evaluation
set: we will also run questions you haven't seen, in both categories, phrased in ways not
shown here.*

## Part 1: example complex questions

| ID | Type | Question |
|---|---|---|
| C1 | Isolation | Which valves must be closed to isolate T4750 for maintenance? List them in the order you would close them, explain the order, and say which connections this drawing does not let you isolate. |
| C2 | Isolation | How would you isolate H1007? If the drawing doesn't give you what you need, say what is missing. |
| C3 | Trip impact | If P4712 trips, which equipment loses flow, and which instrument readings and control loops are affected? |
| C4 | Fail positions | If the actuated valves lose their actuating power, what position does each one go to, and what happens to flow into T4750? Answer strictly from the diagram. |
| C5 | Fail positions / reasoning | If the fail-closed valves shut, would PI4712.01's reading tend to rise or fall? How did you arrive at that answer? |
| C6 | Blocked-in | Can any equipment on this drawing become blocked in, isolated with no visible pressure relief? How did you arrive at this answer? |
| C7 | Relief path | Does H1008 have a path to a pressure relief device? What has to happen for that path to be open? |
| C8 | Loop mapping | Map all connections for PICSA4712.02: where its measurement is taken, every hop to the final element, the final element's fail position, and the piping context of that valve. |
| C9 | Signal tracing | Where does the signal from HS4750.01 go, and which flow does it ultimately start or stop? |
| C10 | Inventory with attributes | How many actuated valves are on this P&ID? For each, give the tag, what operates it, its fail position, and the line it is on. |
| C11 | Inventory with attributes | How many check valves and relief valves are on this drawing? Where is each one, and what does each one protect against? |
| C12 | Line tracing | Trace line 47126 and all of its branches: where each branch starts and ends, and the size of each. |
| C13 | Upstream with recycle | What are all the major equipment upstream of H1008? Account for any recycle. |
| C14 | Parallel paths | Are there parallel paths between P4712 and T4750? Describe each one and when it carries flow. |
| C15 | Process description | Describe the process on this drawing and its main control strategies, strictly from the diagram. |

## Part 2: example rephrasing groups

Within each group, every phrasing asks for the same information. Each one is asked as its own
turn, and all of them should come back with the same facts.

**R1 · Isolating a pump**

- R1a Which valves must be closed to isolate P4712 for maintenance?
- R1b How would you isolate the reciprocating pump?
- R1c I need to pull the 84 kW pump for repair. What do I shut, and is anything left open?
- R1d P-4712 isolation: valve list + any gaps
- R1e Give me the isolation boundary for pump P4712.

**R2 · Fail-position impact**

- R2a If HV4750.01 loses its actuating power, what happens to the flow from P4711 to the tank?
- R2b what happens downstream of the plate exchanger if the hand-switched valve fails?
- R2c HS4750.01 drops out. Does feed still reach T4750?
- R2d Suppose the valve on line 47123 goes to its fail position. Which equipment is cut off from the tank, and is anything left without relief?

**R3 · Loop mapping, rephrased (based on C8)**

- R3a Map all connections for PICSA4712.02.
- R3b where does the pressure controller on the recip pump discharge get its measurement, and what does it move?
- R3c PIC 4712.02: sensor, final element, fail position, which line?
- R3d Which valve closes if the pressure loop on P4712's discharge loses actuator power, and where is that loop's transmitter?

**R4 · Blocked-in, rephrased (based on C6)**

- R4a Can any equipment on this drawing become blocked in with no visible pressure relief?
- R4b anything here that can get trapped between closed valves without a relief valve?
- R4c Which vessels or exchangers could be shut in with nowhere to relieve, given the relief devices shown?
- R4d blocked-in check for this sheet: equipment + reason

## What we'd like you to do

1. **Run every example through your agent**: each complex question and each phrasing, with the
   visible trace (tool calls and results), as before.
2. **Add your own questions**: at least 10 more complex questions of the kind above, and at
   least 5 more rephrasing groups of 4 or more phrasings each, with at least 2 groups built on
   complex questions.
3. **Measure consistency.** Ask every phrasing in each group as a separate turn, 3 times each.
   Report whether the facts agree across phrasings and across repeats, and explain how you
   decide that two answers agree. Optional: if your agent keeps conversation history, also ask
   a group's phrasings as successive turns in one conversation.
4. **Automate it.** Extend your evaluator so the consistency check runs end to end, and report
   the consistency rate with each inconsistency classified by cause.
5. **Write a short note** (under a page): what you changed and why, what still fails, and how
   long you spent.

## Ground rules

- Same as the original brief: no mapping of known phrasings or of these example questions to
  fixed tool calls, in code or in prompts. Changes must be general.
- Keep using an open-source LLM for the agent.
- Keep your real commit history, and include the prompts or specs that shaped this round.
- Plan on about 4 hours. We'd rather see a working core with an honest list of what still
  fails than more machinery.
- Send us a link to the updated repository or branch within 5 days.

If anything is unclear, email us.

--- END FOLLOW-UP EXERCISE ---
