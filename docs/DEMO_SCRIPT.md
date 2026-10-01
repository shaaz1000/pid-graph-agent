# Five-minute demo

```bash
uv run pid-agent-ui
```

The sidebar shows the loaded drawing, the provider and model, and the graph sizes (plant 214
nodes / 376 edges, conceptual 36 nodes / 39 edges). Point at those first: the real C01 file is
loaded through pyDEXPI.

The facts under "what the graph says" below were checked against the graph tools, so they do
not depend on the model. The wording of a live answer, and the exact tool calls the model
chooses, can differ between runs and between models. If an answer differs, open "Tool calls"
and compare with these facts.

## Question 1: entity and connectivity

> What is P4711 connected to, and through which pipes?

What the graph says: upstream `FlowInPipeOffPageConnector-1` through line 47121; downstream
`H1007` (`PlateHeatExchanger-1`) through line 47122. Both DN 80, fluid MNb.

What to point out:

- Open **Tool calls**: `find_entities` resolved the tag, then `get_connections` returned the two pipes.
- Every value in the answer (47121, 47122, DN 80) is in the step 2 result. The model added nothing.
- The green line: "Grounded against graph evidence".

## Question 2: multi-step traversal

> If I follow the piping downstream from the swing check valve, where does the drawing end?

What the graph says: four ends: `BallValve-2`, `BlindFlange-1`, `BlindFlange-2` and
`FlowOutPipeOffPageConnector-1`.

What to point out:

- The valve has no tag; it was found by description.
- One `traverse` call returned everything reachable, with the real end points marked.
- Open **Warnings and graph notes**: the chamber boundary at H1008. The search entered one side
  of the heat exchanger and did not cross to the other.
- The off-page connector leaves the drawing; the answer should not say where it goes.

## Question 3: ambiguity

> What is the nominal diameter at component C1?

What the graph says: five components carry component number C1, on lines 47123, 47124, 47126,
47127 and 47141.

What to point out:

- The tool returned `ambiguous`; the agent asks which one instead of picking.
- The UI lists the five candidates with their ids, ready to copy into a follow-up.
- Follow up with "What is the nominal diameter at GlobeValve-1?" to show it resolving.
  Each question is an independent run, so the follow-up must name the entity itself.

Alternative (false premise): "Since H1008 is rated for 500 kW, which line feeds it?" The graph
says 313.0 kW; the answer should correct the premise and still give line 47126.

## Question 4: instrumentation

> Which valve does HV4750.01 operate, and on which line is that valve installed?

What the graph says: `HV4750.01` (`ActuatingFunction-2`) operates `GlobeValve-2`
(GlobeValve 47123/C1), installed on line 47123, segment S1, DN 80.

What to point out:

- Instrument links are not flow. The tool result describes each link in words
  ("is the actuating function that operates the valve").
- Three calls: find the instrument, read its instrumentation links, read the valve.

## Question 5: a limitation

> For control loop 4712.02: where is the pressure sensed, and which valve does the loop end up acting on?

What the graph says: `PT4712.02` senses at `BlindFlange-2`; the signal goes through
`PICSA4712.02` to `PV4712.02`, which operates `GlobeValve-1`.

What to point out:

- The answer is right, but count the tool calls. In the saved evaluation run this took ten;
  about six were needed.
- Two honest limits show here: following an instrument chain costs one call per hop, and
  nothing tells the model it already has enough evidence. Budgets (8 planning turns, 16 tool
  calls) stop it running away.

Optional sixth, missing data: "How much does heat exchanger H1007 weigh?" The answer should
say the P&ID does not contain a weight.

## Thirty-second close

"The model never sees the drawing. It chooses from seven generic graph operations, plain
Python runs them on the pyDEXPI graph, and every identifier and number in the answer is
checked against what those operations returned. When the graph does not contain something,
such as a weight, a destination off the drawing or a unique match, the system says so. The
evaluation is fifteen questions with expected facts taken from the graph and a deterministic
scorer; the complete run scored fifteen of fifteen on DeepSeek, and I say plainly that the
open-weight model run was cut short by the provider's free quota."
