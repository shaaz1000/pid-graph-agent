"""Builds the second holdout: fresh questions, gold derived from the graph before any inference.

Made after the capability and route-semantics pass, to see whether three failure classes of
the formal evaluation improved. Every fact pattern is checked against the graph. Run from the
project root.
"""
import json
import sys

sys.path.insert(0, "evals/followup")
from followup import gold_facts, matches  # noqa: E402

from pid_agent.agent.tools import GraphTools  # noqa: E402
from pid_agent.graph.service import GraphService  # noqa: E402

tools = GraphTools(GraphService.from_file("data/C01V04-VER.EX01.xml"))
T, P12, P11, H7, H8 = "Tank-1", "ReciprocatingPump-1", "CentrifugalPump-1", "PlateHeatExchanger-1", "TubularHeatExchanger-1"
SV, BFV, GV1, GV2, GV3 = "SpringLoadedGlobeSafetyValve-1", "ButterflyValve-1", "GlobeValve-1", "GlobeValve-2", "GlobeValve-3"
BV1, BV2, BV4, BV5, BF1, BF2 = "BallValve-1", "BallValve-2", "BallValve-4", "BallValve-5", "BlindFlange-1", "BlindFlange-2"
TEE2, TEE3, TEE5, FIN, FOUT = "PipeTee-2", "PipeTee-3", "PipeTee-5", "FlowInPipeOffPageConnector-1", "FlowOutPipeOffPageConnector-1"
PIF4, PSG3, AF3 = "ProcessInstrumentationFunction-4", "ProcessSignalGeneratingFunction-3", "ActuatingFunction-3"


def call(tool, **args): return {"tool": tool, "args": args}
def F(label, *patterns): return {"fact": label, "any_of": list(patterns)}
def prop(e, name, value): return {"p": "has_property", "s": e, "v": value, "q": {"property": name}}
def reach(a, b, direction, **extra): return {"p": "reaches", "s": a, "o": b, "q": {"direction": direction}, **extra}
def bound(e, valve): return F(f"{valve} bounds {e}", {"p": "isolation_boundary_valve", "s": e, "o": valve})
def gap(e, other, kind): return F(f"no valve between {e} and {other}", {"p": "unisolated_connection", "s": e, "o": other, "q": {"kind": kind}})


TEE_BOUNDARY = [bound(TEE5, BV4), bound(TEE5, BV5), gap(TEE5, FOUT, "off_page_connector"), gap(TEE5, H8, "equipment")]
FLOW_VERSUS_LINK = [
    F("no route in the drawn flow direction from H1008 to P4711", {"p": "no_path", "s": H8, "o": P11, "q": {"semantics": "drawn_flow"}}, {"p": "no_path", "s": P11, "o": H8, "q": {"direction": "upstream", "semantics": "drawn_flow"}}),
    F("the two are joined by piping when flow direction is ignored", {"p": "path", "ends": [H8, P11], "q": {"semantics": "topological"}}, {"p": "reaches", "ends": [H8, P11], "q": {"semantics": "topological"}}),
]
VALVE_LOOP = [
    F("TV4750.03 operates GlobeValve 47141/C1", {"p": "operates", "s": AF3, "o": GV3}, {"p": "loop_acts_on", "s": PIF4, "o": GV3}, {"p": "signal_chain", "contains": [AF3, GV3]}),
    F("TICSA4750.03 sends its signal to TV4750.03", {"p": "sends_signal_to", "s": PIF4, "o": AF3}, {"p": "signal_chain", "contains": [PIF4, AF3]}),
    F("the measurement is taken at T4750", {"p": "senses_at", "s": PSG3, "o": T}, {"p": "loop_measured_at", "s": PIF4, "o": T}, {"p": "signal_chain", "contains": [PSG3, T]}),
    F("encoded fail action: fail open", prop(AF3, "failAction", "fail open"), {"p": "loop_acts_on", "o": GV3, "q": {"fail_action": "fail open"}}, {"p": "signal_chain", "contains": [AF3], "q": {"fail_action": "fail open"}}),
]
NOTHING_LEFT = [F("no equipment is downstream of T4750 with the valve treated as closed", {"p": "reaches_nothing", "s": T, "blocked_contains": BV1}, {"p": "no_path", "s": T, "o": P12, "blocked_contains": BV1, "q": {"semantics": "drawn_flow"}})]

Q = []


def add(id, pattern, question, calls, required, alt=(), anchors=(), partial="", forbidden_conclusions=()):
    Q.append({"id": id, "source": "holdout-2", "type": pattern, "question": question, "anchors": list(anchors), "gold_calls": list(calls), "alt_calls": list(alt), "required": required,
              "acceptable_partial": partial, "forbidden_conclusions": list(forbidden_conclusions)})


add("K1", "Isolation completeness", "The tee PipeTee 47126/C9 has to be cut out. Which shut-off valves bound it, and which of its connections reach equipment or leave the drawing with no valve in between?",
    [call("isolation_boundary", entity_id=TEE5)], TEE_BOUNDARY, anchors=[TEE5],
    partial="The two valves without the two unvalved connections.", forbidden_conclusions=["that the tee can be fully isolated", "an order for closing the valves"])
add("K2", "Directional versus topological route", "Following the way the piping is drawn to flow, can anything get from H1008 to P4711? Separately, leaving flow direction aside, are the two joined by piping at all?",
    [call("find_path", source_entity_id=H8, target_entity_id=P11), call("find_path", source_entity_id=H8, target_entity_id=P11, direction="any")], FLOW_VERSUS_LINK,
    alt=[call("find_path", source_entity_id=P11, target_entity_id=H8, direction="upstream"), call("traverse", start_entity_id=H8, direction="both", entity_types=["equipment"])], anchors=[H8, P11],
    partial="One of the two answers.", forbidden_conclusions=["that H1008 feeds or reaches P4711", "that fluid can flow from H1008 to P4711"])
add("K3", "Instrumentation chain entered from the valve", "Start from GlobeValve 47141/C1: which actuating function operates it, which function sends that its signal, where is the measurement for that loop taken, and what fail action is encoded?",
    [call("trace_instrumentation", entity_id=GV3)], VALVE_LOOP, alt=[call("get_properties", ids=[AF3], requested_properties=["failAction"])], anchors=[GV3],
    partial="The actuating function and fail action without the measurement point.", forbidden_conclusions=["the temperature at which the valve acts", "what the valve does to the process"])
add("K4", "Reachability with an item closed", "With BallValve 47124/C4 treated as closed, which equipment is still downstream of T4750? For comparison, which equipment is downstream of T4750 with nothing closed?",
    [call("traverse", start_entity_id=T, direction="downstream", entity_types=["equipment"], blocked_entity_ids=[BV1]), call("traverse", start_entity_id=T, direction="downstream", entity_types=["equipment"])],
    [*NOTHING_LEFT, F("P4712 is downstream of T4750 with nothing closed", reach(T, P12, "downstream", blocked_absent=True), {"p": "path", "s": T, "o": P12, "blocked_absent": True, "q": {"semantics": "drawn_flow"}}),
     F("H1008 is downstream of T4750 with nothing closed", reach(T, H8, "downstream", blocked_absent=True), {"p": "path", "s": T, "o": H8, "blocked_absent": True, "q": {"semantics": "drawn_flow"}})],
    alt=[call("find_path", source_entity_id=T, target_entity_id=P12, blocked_entity_ids=[BV1]), call("find_path", source_entity_id=T, target_entity_id=P12), call("find_path", source_entity_id=T, target_entity_id=H8)], anchors=[T, BV1],
    partial="Either half of the comparison.", forbidden_conclusions=["that the pump is starved, trips or cavitates", "that flow stops"])
DEAD_END = lambda a, b: F(f"the branch {a} -> {b} ends in a dead end and is DN 25", {"p": "line_run", "s": a, "o": b, "q": {"ends_at": "end of the drawn piping", "diameters": ["DN 25"]}})
add("K5", "Branches of a line", "On line 47126, which branches end in a dead end rather than at equipment or at the drawing edge? Give where each starts, where it ends and its size.",
    [call("trace_line", line="47126")], [DEAD_END(TEE2, BV2), DEAD_END(TEE3, BF1), DEAD_END(TEE5, BF2)],
    partial="Some of the three branches.", forbidden_conclusions=["what the dead-end branches are for (drain, vent, test point)"])
LINE_AT_TANK = lambda a, b, line: F(f"line {line}: {a} -> {b}", {"p": "flows_to", "s": a, "o": b, "q": {"lineNumber": line}})
add("K6", "Adjacency with flow direction", "Which piping lines are attached directly to T4750, and for each one, does the drawn flow enter the tank or leave it?",
    [call("get_connections", entity_id=T, relationship="piping")], [LINE_AT_TANK(GV2, T, "47123"), LINE_AT_TANK(SV, T, "47125"), LINE_AT_TANK(GV1, T, "47127"), LINE_AT_TANK(T, BFV, "47124")], anchors=[T],
    partial="Some of the four lines.", forbidden_conclusions=["flow rates", "which lines are in service"])
add("K7", "Upstream reach with a loop", "Which equipment lies upstream of the reciprocating pump? Is the pump itself inside a loop that returns to something upstream of it?",
    [call("traverse", start_entity_id=P12, direction="upstream", entity_types=["equipment"]), call("traverse", start_entity_id=P12, direction="downstream", entity_types=["equipment"])],
    [F("T4750 is upstream of P4712", reach(P12, T, "upstream"), {"p": "path", "s": T, "o": P12, "q": {"semantics": "drawn_flow"}}), F("H1007 is upstream of P4712", reach(P12, H7, "upstream")),
     F("P4711 is upstream of P4712", reach(P12, P11, "upstream")), F("H1008 is upstream of P4712", reach(P12, H8, "upstream")),
     F("the loop: T4750 is also downstream of P4712", reach(P12, T, "downstream"), {"p": "path", "s": P12, "o": T, "q": {"semantics": "drawn_flow"}})],
    alt=[call("find_path", source_entity_id=T, target_entity_id=P12), call("find_path", source_entity_id=P12, target_entity_id=T)], anchors=[P12],
    partial="The upstream equipment without the loop.", forbidden_conclusions=["a recycle rate", "that the loop is operating"])
add("K8", "A boundary with no valves", "For the centrifugal pump: is any shut-off valve drawn on either side of it, and what is it connected to with no valve in between?",
    [call("isolation_boundary", entity_id=P11)],
    [gap(P11, FIN, "off_page_connector"), gap(P11, H7, "equipment"), F("the pump cannot be isolated with the valves drawn", {"p": "fully_valve_bounded", "s": P11, "v": False})], anchors=[P11],
    partial="One of the two unvalved connections.", forbidden_conclusions=["that valves exist beyond the drawing edge", "how the pump is isolated in practice"])

G = []


def group(id, title, based_on, required, calls, phrasings, anchors, alt=()):
    G.append({"id": id, "title": title, "source": "holdout-2", "complex": True, "based_on": based_on, "anchors": list(anchors), "gold_calls": list(calls), "alt_calls": list(alt), "required": required,
              "phrasings": [{"id": f"{id}{chr(97 + i)}", "style": style, "question": q} for i, (style, q) in enumerate(phrasings)]})


group("KG1", "Boundary of a fitting", "K1", TEE_BOUNDARY, [call("isolation_boundary", entity_id=TEE5)],
      [("exact identifier", "PipeTee 47126/C9: bounding shut-off valves, and any connection to equipment or to the drawing edge that has no valve?"),
       ("type and position", "Take the tee immediately upstream of the outgoing off-page connector. What would have to be shut to box it in, and what around it cannot be shut off?"),
       ("property and context", "On line 47126 there is a DN 50 tee whose DN 25 branch leads to valve C10. Which valves close it in, and which of its connections have none?"),
       ("terse operator wording", "47126/C9 tee: isolation valves + unvalved connections")], [TEE5])
group("KG2", "Flow route versus piping link", "K2", FLOW_VERSUS_LINK, [call("find_path", source_entity_id=H8, target_entity_id=P11), call("find_path", source_entity_id=H8, target_entity_id=P11, direction="any")],
      [("exact tags", "H1008 to P4711: does a flow-wise route exist, and are they joined by piping if direction is left aside?"),
       ("type description", "Following the flow arrows, can anything leaving the tubular heat exchanger arrive at the centrifugal pump? And is there any pipe connection between those two regardless of direction?"),
       ("property and context", "Take the exchanger that line 47127 comes out of and the pump that line 47121 runs into. Is the pump downstream of the exchanger? Are the two linked by pipework at all?"),
       ("terse operator wording", "H-1008 -> P-4711: flow path yes/no; any piping link yes/no")], [H8, P11],
      alt=[call("find_path", source_entity_id=P11, target_entity_id=H8, direction="upstream"), call("traverse", start_entity_id=H8, direction="both", entity_types=["equipment"])])
group("KG3", "A loop entered from its valve", "K3", VALVE_LOOP, [call("trace_instrumentation", entity_id=GV3)],
      [("exact identifier", "GlobeValve 47141/C1: operating function, the function that signals it, the measurement point of the loop, and the encoded fail action?"),
       ("type and position", "The globe valve on the line that leaves H1008 toward the drawing edge: give its whole control chain from where the measurement is taken to the valve, with the fail action."),
       ("property", "One actuator on this sheet is encoded to fail open. Which valve does it operate, what sends it its signal, and where does that loop measure?"),
       ("terse operator wording", "47141/C1: loop members, tap point, fail action")], [GV3], alt=[call("get_properties", ids=[AF3], requested_properties=["failAction"])])
group("KG4", "What remains downstream with a valve closed", "K4", NOTHING_LEFT, [call("traverse", start_entity_id=T, direction="downstream", entity_types=["equipment"], blocked_entity_ids=[BV1])],
      [("exact identifier", "Treat BallValve 47124/C4 as closed. Which equipment is still downstream of T4750?"),
       ("type description", "Shut the ball valve on the suction side of the reciprocating pump. Which equipment can the tank still reach in the flow direction?"),
       ("property and context", "Suppose the DN 50 valve between the reducer and P4712 is closed: is any equipment left downstream of the tank?"),
       ("terse operator wording", "47124/C4 shut: any equipment downstream of T-4750?")], [T, BV1],
      alt=[call("find_path", source_entity_id=T, target_entity_id=P12, blocked_entity_ids=[BV1])])

problems = 0
for item in [*Q, *G]:
    facts = gold_facts(tools, item["gold_calls"])
    wider = gold_facts(tools, [*item["gold_calls"], *item["alt_calls"]])
    for required in item["required"]:
        for pattern in required["any_of"]:
            if not any(matches(pattern, f) for f in wider):
                problems += 1
                print("PATTERN MATCHES NO GRAPH FACT:", item["id"], required["fact"], pattern)
        if not any(matches(p, f) for p in required["any_of"] for f in facts):
            problems += 1
            print("NOT DERIVED BY GOLD CALLS:", item["id"], required["fact"])
print(len(Q), "holdout questions;", len(G), "groups;", sum(len(g["phrasings"]) for g in G), "phrasings; problems:", problems)
if not problems:
    note = "Second holdout on C01, written after the capability and route-semantics pass and frozen before any model call. Gold is derived from the graph by build_holdout.py. Not part of the official follow-up scores."
    json.dump({"description": note, "pid": "data/C01V04-VER.EX01.xml", "questions": Q}, open("evals/followup/holdout-2/questions.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"description": note, "pid": "data/C01V04-VER.EX01.xml", "groups": G}, open("evals/followup/holdout-2/groups.json", "w"), indent=1, ensure_ascii=False)
