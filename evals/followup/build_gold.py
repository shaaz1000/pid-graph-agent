"""Builds the follow-up gold files. Every fact pattern is checked against the graph before writing."""
import json, sys
sys.path.insert(0, "evals/followup")
from followup import gold_facts, matches
from pid_agent.agent.tools import GraphTools
from pid_agent.graph.service import GraphService

tools = GraphTools(GraphService.from_file("data/C01V04-VER.EX01.xml"))
T, P12, P11, H7, H8 = "Tank-1", "ReciprocatingPump-1", "CentrifugalPump-1", "PlateHeatExchanger-1", "TubularHeatExchanger-1"
SV, GV1, GV2, GV3, BFV, CHK, RED = "SpringLoadedGlobeSafetyValve-1", "GlobeValve-1", "GlobeValve-2", "GlobeValve-3", "ButterflyValve-1", "SwingCheckValve-1", "PipeReducer-1"
BV1, BV2, BV3, BV4, BV5, BF1, BF2 = "BallValve-1", "BallValve-2", "BallValve-3", "BallValve-4", "BallValve-5", "BlindFlange-1", "BlindFlange-2"
AF1, AF2, AF3 = "ActuatingFunction-1", "ActuatingFunction-2", "ActuatingFunction-3"
PIF1, PIF2, PIF3, PIF4 = (f"ProcessInstrumentationFunction-{i}" for i in (1, 2, 3, 4))
PSG1, PSG2, PSG3 = (f"ProcessSignalGeneratingFunction-{i}" for i in (1, 2, 3))
TEE1, TEE2, TEE3, TEE4, TEE5 = (f"PipeTee-{i}" for i in (1, 2, 3, 4, 5))
FIN, FOUT = "FlowInPipeOffPageConnector-1", "FlowOutPipeOffPageConnector-1"

def call(tool, **args): return {"tool": tool, "args": args}
def F(label, *patterns): return {"fact": label, "any_of": list(patterns)}
def U(*categories): return {"unknown": list(categories)}
def FU(label, categories, *patterns): return {"fact": label, "any_of": list(patterns), "unknown": list(categories)}
def prop(e, name, value): return {"p": "has_property", "s": e, "v": value, "q": {"property": name}}
def boundary(e, valve, *alt): return F(f"{valve} bounds {e}", {"p": "isolation_boundary_valve", "s": e, "o": valve}, *alt)
def fail(af, value, valve): return F(f"fail action of {af}: {value}", prop(af, "failAction", value), {"p": "loop_acts_on", "o": valve, "q": {"fail_action": value}}, {"p": "signal_chain", "contains": [af], "q": {"fail_action": value}})
def acts(pif, af, valve): return F(f"{af} operates {valve}", {"p": "operates", "s": af, "o": valve}, {"p": "loop_acts_on", "s": pif, "o": valve}, {"p": "signal_chain", "contains": [af, valve]})
def measured(pif, psg, place): return F(f"{psg} measures at {place}", {"p": "senses_at", "s": psg, "o": place}, {"p": "loop_measured_at", "s": pif, "o": place}, {"p": "signal_chain", "contains": [psg, place]})
def on_line(valve, line): return F(f"{valve} is on line {line}", prop(valve, "lineNumber", line), {"p": "loop_acts_on", "o": valve, "q": {"line": line}}, {"p": "flows_to", "s": valve, "q": {"lineNumber": line}}, {"p": "flows_to", "o": valve, "q": {"lineNumber": line}}, {"p": "isolation_boundary_valve", "o": valve, "q": {"line": line}})
def pipe(a, b, line, dn): return F(f"pipe {a} -> {b}: line {line}, {dn}", {"p": "flows_to", "s": a, "o": b, "q": {"lineNumber": line, "nominalDiameterRepresentation": dn}})
def reach(a, b, direction, **extra): return {"p": "reaches", "s": a, "o": b, "q": {"direction": direction}, **extra}
def open_end(e, line): return F(f"line {line} at {e} leaves the drawing (open end)", {"p": "open_end", "s": e, "q": {"lineNumber": line}}, {"p": "unisolated_connection", "s": e, "q": {"kind": "open_end", "line": line}}, {"p": "line_meets_line", "s": e, "v": line})
def is_type(e, t): return F(f"{e} is a {t}", {"p": "is_a", "s": e, "v": t})

LOOP = lambda name: call("trace_instrumentation", entity_id=name)
CONN = lambda e, rel="all": call("get_connections", entity_id=e, relationship=rel)
PROPS = lambda *ids: call("get_properties", ids=list(ids))
ISO = lambda e: call("isolation_boundary", entity_id=e)

Q = []
def add(id, type, question, calls, required, alt=(), anchors=(), source=None, notes=None):
    Q.append({"id": id, "source": source or ("provided" if id.startswith("C") else "own"), "type": type, "question": question, "anchors": list(anchors),
              "gold_calls": list(calls), "alt_calls": list(alt), "required": required, **({"notes": notes} if notes else {})})

add("C1", "Isolation", "Which valves must be closed to isolate T4750 for maintenance? List them in the order you would close them, explain the order, and say which connections this drawing does not let you isolate.",
    [ISO(T)], [boundary(T, GV2, {"p": "flows_to", "s": GV2, "o": T}), boundary(T, GV1, {"p": "flows_to", "s": GV1, "o": T}), boundary(T, BFV, {"p": "flows_to", "s": T, "o": BFV}),
               F("the line from SV 104.01 has no isolation valve", {"p": "relief_device_on_boundary", "s": T, "o": SV}, {"p": "flows_to", "s": SV, "o": T}), U("operating_procedure")],
    alt=[CONN(T, "piping")], anchors=[T], notes="A P&ID does not encode a closure order; the answer must say so instead of giving one.")
add("C2", "Isolation", "How would you isolate H1007? If the drawing doesn't give you what you need, say what is missing.",
    [ISO(H7)], [boundary(H7, GV2, {"p": "flows_to", "s": H7, "o": GV2}), F("no valve between H1007 and P4711", {"p": "unisolated_connection", "s": H7, "o": P11}, {"p": "flows_to", "s": P11, "o": H7}),
                open_end(H7, "47130"), open_end(H7, "47131"), F("H1007 cannot be fully isolated with the valves drawn", {"p": "fully_valve_bounded", "s": H7, "v": False}, {"p": "unisolated_connection", "s": H7, "q": {"kind": "open_end"}})],
    alt=[CONN(H7, "piping")], anchors=[H7])
add("C3", "Trip impact", "If P4712 trips, which equipment loses flow, and which instrument readings and control loops are affected?",
    [call("traverse", start_entity_id=P12, direction="downstream", entity_types=["equipment"]), LOOP(BF1), LOOP(BF2)],
    [F("H1008 is downstream of P4712", reach(P12, H8, "downstream"), {"p": "path", "s": P12, "o": H8}), F("T4750 is downstream of P4712", reach(P12, T, "downstream"), {"p": "path", "s": P12, "o": T}),
     measured(PIF1, PSG1, BF1), measured(PIF2, PSG2, BF2), acts(PIF2, AF1, GV1), U("process_behaviour", "operating_state")],
    alt=[call("find_path", source_entity_id=P12, target_entity_id=H8), call("find_path", source_entity_id=P12, target_entity_id=T)], anchors=[P12],
    notes="Downstream reach and the instruments measuring on it are graph facts; that flow is lost or a reading changes is process behaviour.")
BLOCKED = lambda valve: F(f"what remains connected with {valve} treated as closed", {"p": ["reaches", "path", "no_path"], "blocked_contains": valve})
add("C4", "Fail positions", "If the actuated valves lose their actuating power, what position does each one go to, and what happens to flow into T4750? Answer strictly from the diagram.",
    [call("list_entities", entity_type="ActuatingFunction", properties=["failAction"]), LOOP(AF1), LOOP(AF2), LOOP(AF3),
     call("traverse", start_entity_id=T, direction="upstream", entity_types=["equipment"], blocked_entity_ids=[GV1, GV2])],
    [fail(AF1, "fail close", GV1), fail(AF2, "fail close", GV2), fail(AF3, "fail open", GV3), acts(PIF2, AF1, GV1), acts(PIF3, AF2, GV2), acts(PIF4, AF3, GV3),
     BLOCKED(GV2), BLOCKED(GV1), U("process_behaviour", "operating_state")], anchors=[T],
    notes="Encoded fail actions are direct facts; what stays connected with the fail-closed valves blocked is derived; actual flow is not in the drawing.")
add("C5", "Fail positions / reasoning", "If the fail-closed valves shut, would PI4712.01's reading tend to rise or fall? How did you arrive at that answer?",
    [call("list_entities", entity_type="ActuatingFunction", properties=["failAction"]), LOOP(PIF1), LOOP(AF1), LOOP(AF2),
     call("find_path", source_entity_id=P12, target_entity_id=T, all_paths=True, blocked_entity_ids=[GV1, GV2])],
    [fail(AF1, "fail close", GV1), fail(AF2, "fail close", GV2), measured(PIF1, PSG1, BF1), BLOCKED(GV1), U("process_behaviour")], anchors=[PIF1],
    notes="Whether a pressure reading rises or falls cannot be determined from a P&ID; the expected answer says so and gives the topology it can establish.")
add("C6", "Blocked-in", "Can any equipment on this drawing become blocked in, isolated with no visible pressure relief? How did you arrive at this answer?",
    [ISO(T), ISO(P12), ISO(H7), ISO(H8), ISO(P11)],
    [F("T4750 is fully bounded by valves", {"p": "fully_valve_bounded", "s": T, "v": True}), F("no relief device stays connected to T4750 inside that boundary", {"p": "relief_path_inside_boundary", "s": T, "v": False}),
     F("P4712 is fully bounded by valves", {"p": "fully_valve_bounded", "s": P12, "v": True}), F("P4712 keeps a path to SV 104.01 inside its boundary", {"p": "relief_path_inside_boundary", "s": P12, "v": True}),
     F("H1007 cannot be closed in by the valves drawn", {"p": "fully_valve_bounded", "s": H7, "v": False}), F("H1008 cannot be closed in by the valves drawn", {"p": "fully_valve_bounded", "s": H8, "v": False}),
     F("P4711 cannot be closed in by the valves drawn", {"p": "fully_valve_bounded", "s": P11, "v": False})], anchors=[],
    notes="A statement about drawn valves and relief devices only; it does not say the equipment is unsafe.")
add("C7", "Relief path", "Does H1008 have a path to a pressure relief device? What has to happen for that path to be open?",
    [call("find_path", source_entity_id=H8, target_entity_id=SV, direction="any", all_paths=True)],
    [F("a drawn route joins H1008 and SV 104.01", {"p": "path", "ends": [H8, SV]}, {"p": "reaches", "ends": [H8, SV]}),
     F("the route to the inlet of SV 104.01 passes BallValve 47126/C7", {"p": "path", "ends": [H8, SV], "contains": [BV4, TEE1]}, {"p": "isolation_boundary_valve", "s": H8, "o": BV4}),
     U("operating_state", "process_behaviour")], alt=[call("traverse", start_entity_id=H8, direction="both"), ISO(H8)], anchors=[H8],
    notes="Two undirected routes join them: one through T4750 to the discharge side of the relief device, one against the drawn flow through 47126/C7 to its inlet. Whether that valve is open, and when the device lifts, is not in the P&ID.")
add("C8", "Loop mapping", "Map all connections for PICSA4712.02: where its measurement is taken, every hop to the final element, the final element's fail position, and the piping context of that valve.",
    [LOOP(PIF2)], [measured(PIF2, PSG2, BF2), F("PT4712.02 feeds PICSA4712.02", {"p": "measurement_input_to", "s": PSG2, "o": PIF2}, {"p": "signal_chain", "contains": [PSG2, PIF2]}),
                   F("PICSA4712.02 signals PV4712.02", {"p": "sends_signal_to", "s": PIF2, "o": AF1}, {"p": "signal_chain", "contains": [PIF2, AF1]}), acts(PIF2, AF1, GV1), fail(AF1, "fail close", GV1), on_line(GV1, "47127")],
    alt=[CONN(GV1), PROPS(GV1, AF1), ISO(H8)], anchors=[PIF2])
add("C9", "Signal tracing", "Where does the signal from HS4750.01 go, and which flow does it ultimately start or stop?",
    [LOOP(PIF3), CONN(GV2, "piping")], [F("HS4750.01 signals HV4750.01", {"p": "sends_signal_to", "s": PIF3, "o": AF2}, {"p": "signal_chain", "contains": [PIF3, AF2]}), acts(PIF3, AF2, GV2), on_line(GV2, "47123"),
                                        F("the operated valve sits between H1007 and T4750", {"p": "flows_to", "s": H7, "o": GV2}, {"p": "flows_to", "s": GV2, "o": T}, {"p": ["path", "no_path", "reaches"], "blocked_contains": GV2})],
    alt=[PROPS(GV2), ISO(T), call("find_path", source_entity_id=H7, target_entity_id=T, blocked_entity_ids=[GV2])], anchors=[PIF3])
add("C10", "Inventory with attributes", "How many actuated valves are on this P&ID? For each, give the tag, what operates it, its fail position, and the line it is on.",
    [LOOP(AF1), LOOP(AF2), LOOP(AF3)], [acts(PIF2, AF1, GV1), acts(PIF3, AF2, GV2), acts(PIF4, AF3, GV3), fail(AF1, "fail close", GV1), fail(AF2, "fail close", GV2), fail(AF3, "fail open", GV3),
                                        on_line(GV1, "47127"), on_line(GV2, "47123"), on_line(GV3, "47141")],
    alt=[PROPS(GV1, GV2, GV3, AF1, AF2, AF3), CONN(GV1), CONN(GV2), CONN(GV3), ISO(H8), ISO(T)], anchors=[])
add("C11", "Inventory with attributes", "How many check valves and relief valves are on this drawing? Where is each one, and what does each one protect against?",
    [call("list_entities", entity_type="CheckValve", properties=["lineNumber"]), call("list_entities", entity_type="SafetyValveOrFitting", properties=["lineNumber", "setPressureHigh"]), CONN(CHK, "piping"), CONN(SV, "piping")],
    [is_type(CHK, "SwingCheckValve"), is_type(SV, "SpringLoadedGlobeSafetyValve"), on_line(CHK, "47124"), on_line(SV, "47125"), U("purpose_or_intent")], anchors=[],
    notes="Type, line and neighbours are in the drawing; what a device protects against is design intent, which a P&ID does not state.")
RUN = lambda a, b: F(f"run {a} -> {b}", {"p": "line_run", "s": a, "o": b}, {"p": "flows_to", "s": a, "o": b, "q": {"lineNumber": "47126"}})
add("C12", "Line tracing", "Trace line 47126 and all of its branches: where each branch starts and ends, and the size of each.",
    [call("trace_line", line="47126")], [RUN(P12, TEE2), RUN(TEE2, BV2), RUN(TEE2, TEE1), RUN(TEE1, TEE3), F(f"run {TEE3} -> {BF1} through {BV3}", {"p": "line_run", "s": TEE3, "o": BF1}), F(f"run {TEE3} -> {TEE4} through {BV4}", {"p": "line_run", "s": TEE3, "o": TEE4}),
                                         RUN(TEE4, H8), RUN(TEE4, TEE5), F(f"run {TEE5} -> {BF2} through {BV5}", {"p": "line_run", "s": TEE5, "o": BF2}), RUN(TEE5, FOUT),
                                         F("the DN 25 branches are reported with their size", {"p": "line_run", "s": TEE3, "o": BF1, "q": {"diameters": ["DN 25"]}}, prop(BV3, "nominalDiameterRepresentation", "DN 25"), {"p": "flows_to", "s": TEE3, "o": BV3, "q": {"nominalDiameterRepresentation": "DN 25"}})],
    alt=[PROPS(BV3), CONN(TEE3, "piping")], anchors=[])
add("C13", "Upstream with recycle", "What are all the major equipment upstream of H1008? Account for any recycle.",
    [call("traverse", start_entity_id=H8, direction="upstream", entity_types=["equipment"]), call("traverse", start_entity_id=H8, direction="downstream", entity_types=["equipment"])],
    [F("P4712 is upstream of H1008", reach(H8, P12, "upstream"), {"p": "path", "s": P12, "o": H8}), F("T4750 is upstream of H1008", reach(H8, T, "upstream")), F("H1007 is upstream of H1008", reach(H8, H7, "upstream")), F("P4711 is upstream of H1008", reach(H8, P11, "upstream")),
     F("recycle: T4750 is also downstream of H1008", reach(H8, T, "downstream"), {"p": "path", "s": H8, "o": T}, reach(T, H8, "downstream"))],
    alt=[call("find_path", source_entity_id=P12, target_entity_id=H8), call("find_path", source_entity_id=H8, target_entity_id=T), call("traverse", start_entity_id=T, direction="downstream", entity_types=["equipment"])], anchors=[H8])
add("C14", "Parallel paths", "Are there parallel paths between P4712 and T4750? Describe each one and when it carries flow.",
    [call("find_path", source_entity_id=P12, target_entity_id=T, all_paths=True)],
    [F("route through SV 104.01 (line 47125)", {"p": "path", "s": P12, "o": T, "contains": [SV]}), F("route through H1008 and GlobeValve 47127/C1", {"p": "path", "s": P12, "o": T, "contains": [H8, GV1]}), U("operating_state", "process_behaviour")], anchors=[P12, T],
    notes="Both routes are derived facts; when each carries flow depends on valve positions and pressure, which the P&ID does not give.")
add("C15", "Process description", "Describe the process on this drawing and its main control strategies, strictly from the diagram.",
    [call("list_entities", entity_type="equipment"), LOOP(PIF2), LOOP(PIF3), LOOP(PIF4)],
    [is_type(P11, "CentrifugalPump"), is_type(H7, "PlateHeatExchanger"), is_type(T, "Tank"), is_type(P12, "ReciprocatingPump"), is_type(H8, "TubularHeatExchanger"), acts(PIF2, AF1, GV1), acts(PIF3, AF2, GV2), acts(PIF4, AF3, GV3),
     U("purpose_or_intent", "process_behaviour", "operating_state", "other")], anchors=[],
    notes="Equipment, piping and loops can be described from the graph; the intent of a control strategy is not stated in a P&ID.")

# ----- our own complex questions
add("X1", "Line walk with size change", "Walk the suction of P4712 back to the tank: every component in order, and where the pipe size changes.",
    [call("find_path", source_entity_id=T, target_entity_id=P12)],
    [F("the route T4750 -> P4712 in order", {"p": "path", "s": T, "o": P12, "q": {"entities": [T, BFV, CHK, RED, BV1, P12]}}, {"p": "path", "s": P12, "o": T, "q": {"entities": [P12, BV1, RED, CHK, BFV, T]}}),
     pipe(CHK, RED, "47124", "DN 80"), pipe(RED, BV1, "47124", "DN 50")], alt=[call("find_path", source_entity_id=P12, target_entity_id=T, direction="upstream")], anchors=[T, P12])
add("X2", "Reachability with one valve closed", "If the valve at 47126/C7 is closed, which equipment can P4712's discharge still reach, and which can it no longer reach?",
    [call("traverse", start_entity_id=P12, direction="downstream", entity_types=["equipment"], blocked_entity_ids=[BV4]), call("find_path", source_entity_id=P12, target_entity_id=H8, blocked_entity_ids=[BV4])],
    [F("T4750 is still reachable with the valve closed", reach(P12, T, "downstream", blocked_contains=BV4), {"p": "path", "s": P12, "o": T, "blocked_contains": BV4}),
     F("H1008 is no longer reachable with the valve closed", {"p": "no_path", "s": P12, "o": H8, "blocked_contains": BV4})],
    alt=[call("find_path", source_entity_id=P12, target_entity_id=T, blocked_entity_ids=[BV4])], anchors=[P12, BV4])
END = lambda e: F(f"{e} is an end of the drawn piping", {"p": "terminal", "s": e}, {"p": "closed_end_in_region", "o": e}, {"p": "line_run", "o": e}, {"p": "isolation_boundary_valve", "o": e, "q": {"nothing_drawn_beyond": True}})
add("X4", "Inventory of pipe ends", "List every place where piping ends on this sheet, and separate dead ends from connections that leave the drawing. Give the line for each.",
    [call("traverse", start_entity_id=P12, direction="downstream"), CONN(H7, "piping"), CONN(H8, "piping"), CONN(GV3, "piping")],
    [END(BF1), END(BF2), END(BV2), F("the piping leaves the drawing at FlowOutPipeOffPageConnector-1", {"p": "terminal", "s": FOUT}, {"p": "line_run", "o": FOUT}, {"p": "unisolated_connection", "o": FOUT}, {"p": "reaches", "o": FOUT}),
     open_end(H7, "47130"), open_end(H7, "47131"), open_end(H8, "47140"), open_end(GV3, "47141")],
    alt=[call("trace_line", line="47126"), ISO(P12), ISO(H8), ISO(H7), ISO(GV3)], anchors=[])
add("X5", "Full route with lines", "Give the full route from the off-page inlet to T4750 with every component, line number and diameter.",
    [call("find_path", source_entity_id=FIN, target_entity_id=T)],
    [F("the route in order", {"p": "path", "s": FIN, "o": T, "q": {"entities": [FIN, P11, H7, GV2, T]}}), pipe(FIN, P11, "47121", "DN 80"), pipe(P11, H7, "47122", "DN 80"), pipe(H7, GV2, "47123", "DN 80"), pipe(GV2, T, "47123", "DN 80")], anchors=[FIN, T])
add("X6", "Instruments on a section of piping", "Which instruments take their measurement on the discharge piping of P4712, at which component, and what does each measurement feed?",
    [LOOP(BF1), LOOP(BF2)], [measured(PIF1, PSG1, BF1), measured(PIF2, PSG2, BF2), F("PT4712.01 feeds PI4712.01", {"p": "measurement_input_to", "s": PSG1, "o": PIF1}, {"p": "signal_chain", "contains": [PSG1, PIF1]}),
                             F("PT4712.02 feeds PICSA4712.02", {"p": "measurement_input_to", "s": PSG2, "o": PIF2}, {"p": "signal_chain", "contains": [PSG2, PIF2]})], anchors=[P12])
add("X7", "Recycle loop", "Is T4750 part of a recycle loop? Show the route out of the tank and the route back to it.",
    [call("find_path", source_entity_id=T, target_entity_id=P12), call("find_path", source_entity_id=P12, target_entity_id=T, all_paths=True)],
    [F("a route leads from T4750 to P4712", {"p": "path", "s": T, "o": P12}, reach(T, P12, "downstream")), F("a route leads from P4712 back to T4750", {"p": "path", "s": P12, "o": T}, reach(P12, T, "downstream"))],
    alt=[call("traverse", start_entity_id=T, direction="downstream", entity_types=["equipment"]), call("traverse", start_entity_id=P12, direction="downstream", entity_types=["equipment"])], anchors=[T, P12])
add("X9", "Loop mapping", "Map TICSA4750.03 end to end: where the temperature is measured, the valve it acts on, that valve's fail position, and where the valve's line goes.",
    [LOOP(PIF4), CONN(GV3, "piping")], [measured(PIF4, PSG3, T), acts(PIF4, AF3, GV3), fail(AF3, "fail open", GV3), on_line(GV3, "47141"),
                                        FU("line 47141 leaves the drawing after the valve", ["off_drawing"], {"p": "open_end", "s": GV3, "q": {"lineNumber": "47141"}}, {"p": "unisolated_connection", "q": {"kind": "open_end", "line": "47141"}})],
    alt=[PROPS(GV3, AF3), ISO(GV3), ISO(H8)], anchors=[PIF4])
add("X10", "Connections that leave the drawing", "Which equipment has a pipe whose other end is not on this drawing, and on which lines?",
    [CONN(H7, "piping"), CONN(H8, "piping")], [open_end(H7, "47130"), open_end(H7, "47131"), open_end(H8, "47140")], alt=[ISO(H7), ISO(H8), call("trace_line", line="47126")], anchors=[])
add("X11", "Comparison by property", "Compare the two pumps: design shaft power and design pressure head of each. Which is higher in each case?",
    [call("list_entities", entity_type="pump", properties=["designShaftPower", "designPressureHead"])],
    [F("P4712 design shaft power", prop(P12, "designShaftPower", "84.0 kW")), F("P4711 design shaft power", {"p": "has_property", "s": P11, "q": {"property": "designShaftPower"}}),
     F("P4712 design pressure head", prop(P12, "designPressureHead", "40.0 m")), F("P4711 design pressure head", {"p": "has_property", "s": P11, "q": {"property": "designPressureHead"}})], anchors=[P11, P12])
add("X12", "Chamber boundary", "Can flow pass from line 47126 through H1008 into line 47141? Explain from the drawing.",
    [call("find_path", source_entity_id=TEE4, target_entity_id=GV3)],
    [F("no route from the 47126 side to the valve on 47141", {"p": "no_path", "o": GV3}, {"p": "chamber_boundary", "s": H8})], alt=[call("find_path", source_entity_id=P12, target_entity_id=GV3)], anchors=[H8])
add("X13", "Routes with one valve closed", "With the valve at 47127/C1 closed, is there still a route from P4712 to T4750? What lies on it?",
    [call("find_path", source_entity_id=P12, target_entity_id=T, all_paths=True, blocked_entity_ids=[GV1])],
    [F("one route remains, through SV 104.01", {"p": "path", "s": P12, "o": T, "contains": [SV], "blocked_contains": GV1}, reach(P12, T, "downstream", blocked_contains=GV1))],
    alt=[call("traverse", start_entity_id=P12, direction="downstream", blocked_entity_ids=[GV1])], anchors=[P12, T, GV1])
SMALL = lambda v, line: F(f"{v} is on DN 25 piping, line {line}", prop(v, "nominalDiameterRepresentation", "DN 25"))
add("X14", "Inventory constrained by a property", "Which valves sit on DN 25 piping, and on which line is each?",
    [call("list_entities", entity_type="valve", properties=["lineNumber"], property_filter={"nominalDiameterRepresentation": "DN 25"})],
    [SMALL(BV2, "47126"), SMALL(BV3, "47126"), SMALL(BV5, "47126"), SMALL(SV, "47125"), on_line(SV, "47125"), on_line(BV3, "47126")], alt=[CONN(SV, "piping"), CONN(BV3, "piping"), ISO(P12)], anchors=[])

# ----- rephrasing groups
G = []
def group(id, title, required, calls, phrasings, anchors, complex=False, alt=(), source=None, own=None):
    """``required`` is the target the whole group shares. ``own`` gives a phrasing its own gold when its literal wording asks for less."""
    G.append({"id": id, "title": title, "source": source or ("provided" if id.startswith("R") else "own"), "complex": complex, "anchors": list(anchors), "gold_calls": list(calls), "alt_calls": list(alt), "required": required,
              "phrasings": [{"id": f"{id}{chr(97 + i)}", "question": q, **({"required": own[f"{id}{chr(97 + i)}"]} if own and f"{id}{chr(97 + i)}" in own else {})} for i, q in enumerate(phrasings)]})

group("R1", "Isolating a pump", [boundary(P12, BV1, {"p": "flows_to", "s": BV1, "o": P12}), boundary(P12, BV2), boundary(P12, BV3), boundary(P12, BV4),
                                 F("the relief line to SV 104.01 has no isolation valve", {"p": "relief_device_on_boundary", "s": P12, "o": SV}, {"p": "flows_to", "s": TEE1, "o": SV})], [ISO(P12)],
      ["Which valves must be closed to isolate P4712 for maintenance?", "How would you isolate the reciprocating pump?", "I need to pull the 84 kW pump for repair. What do I shut, and is anything left open?",
       "P-4712 isolation: valve list + any gaps", "Give me the isolation boundary for pump P4712."], [P12], complex=True, alt=[CONN(P12, "piping"), CONN(TEE1, "piping")])
group("R2", "Fail-position impact", [fail(AF2, "fail close", GV2), acts(PIF3, AF2, GV2), BLOCKED(GV2)], [LOOP(AF2), call("find_path", source_entity_id=P11, target_entity_id=T, blocked_entity_ids=[GV2])],
      ["If HV4750.01 loses its actuating power, what happens to the flow from P4711 to the tank?", "what happens downstream of the plate exchanger if the hand-switched valve fails?", "HS4750.01 drops out. Does feed still reach T4750?",
       "Suppose the valve on line 47123 goes to its fail position. Which equipment is cut off from the tank, and is anything left without relief?"], [], complex=True)
group("R3", "Loop mapping, rephrased", [measured(PIF2, PSG2, BF2), acts(PIF2, AF1, GV1), fail(AF1, "fail close", GV1), on_line(GV1, "47127")], [LOOP(PIF2)],
      ["Map all connections for PICSA4712.02.", "where does the pressure controller on the recip pump discharge get its measurement, and what does it move?", "PIC 4712.02: sensor, final element, fail position, which line?",
       "Which valve closes if the pressure loop on P4712's discharge loses actuator power, and where is that loop's transmitter?"], [PIF2], complex=True, alt=[CONN(GV1), PROPS(GV1, AF1), ISO(H8)],
      # "Map all connections for X" can be read literally: the links of X itself. That reading is
      # a correct answer to R3a, though it is less than the loop the group as a whole asks for.
      own={"R3a": [F("PT4712.02 feeds PICSA4712.02", {"p": "measurement_input_to", "s": PSG2, "o": PIF2}, {"p": "signal_chain", "contains": [PSG2, PIF2]}),
                   F("PICSA4712.02 signals PV4712.02", {"p": "sends_signal_to", "s": PIF2, "o": AF1}, {"p": "signal_chain", "contains": [PIF2, AF1]})]})
group("R4", "Blocked-in, rephrased", [F("T4750 is fully bounded by valves", {"p": "fully_valve_bounded", "s": T, "v": True}), F("no relief device stays connected to T4750 inside that boundary", {"p": "relief_path_inside_boundary", "s": T, "v": False}),
                                      F("P4712 keeps a path to SV 104.01 inside its boundary", {"p": "relief_path_inside_boundary", "s": P12, "v": True})], [ISO(T), ISO(P12)],
      ["Can any equipment on this drawing become blocked in with no visible pressure relief?", "anything here that can get trapped between closed valves without a relief valve?",
       "Which vessels or exchangers could be shut in with nowhere to relieve, given the relief devices shown?", "blocked-in check for this sheet: equipment + reason"], [], complex=True)
group("G1", "Isolating a heat exchanger", [boundary(H8, BV4), boundary(H8, BV5), boundary(H8, GV1, {"p": "flows_to", "s": H8, "o": GV1}), boundary(H8, GV3, {"p": "flows_to", "s": H8, "o": GV3}),
                                           F("no valve before the piping leaves the drawing at the off-page connector", {"p": "unisolated_connection", "s": H8, "o": FOUT}), open_end(H8, "47140")], [ISO(H8)],
      ["Which valves isolate H1008, and which of its connections cannot be isolated on this drawing?", "isolation boundary for the tubular heat exchanger", "H-1008 maintenance: what do I close, any open ends?",
       "I need to take the exchanger fed from line 47126 out of service. Valve list and gaps, please."], [H8], complex=True, alt=[CONN(H8, "piping")])
group("G2", "Reach with one valve closed", [F("T4750 is still reachable from P4712 with the valve closed", reach(P12, T, "downstream", blocked_contains=BV4), {"p": "path", "s": P12, "o": T, "blocked_contains": BV4}),
                                            F("H1008 is no longer reachable from P4712 with the valve closed", {"p": "no_path", "s": P12, "o": H8, "blocked_contains": BV4})],
      [call("traverse", start_entity_id=P12, direction="downstream", entity_types=["equipment"], blocked_entity_ids=[BV4]), call("find_path", source_entity_id=P12, target_entity_id=H8, blocked_entity_ids=[BV4])],
      ["If the valve at 47126/C7 is shut, can P4712 still reach T4750, and can it still reach H1008?", "recip pump discharge with C7 on line 47126 closed: does it still get to the tank? to the tubular exchanger?",
       "Close the ball valve between P4712 and H1008. Which of T4750 and H1008 can the 84 kW pump still reach?", "47126/C7 shut: P-4712 to T-4750 still connected? P-4712 to H-1008?"], [P12, BV4], complex=True,
      alt=[call("find_path", source_entity_id=P12, target_entity_id=T, blocked_entity_ids=[BV4])])
group("G3", "Temperature loop", [measured(PIF4, PSG3, T), acts(PIF4, AF3, GV3), fail(AF3, "fail open", GV3), on_line(GV3, "47141")], [LOOP(PIF4)],
      ["Map TICSA4750.03: where it measures, the valve it acts on, the fail position and the line.", "where does the temperature controller on the tank take its measurement, and what does it move?", "TIC 4750.03: sensor, final element, fail position, which line?",
       "Which valve opens if the temperature loop on T4750 loses actuator power, on which line is it, and where is that loop's sensor?"], [PIF4], complex=True, alt=[CONN(GV3), PROPS(GV3, AF3), ISO(H8)])
group("G4", "An item by tag, type, context and shorthand", [F("design shaft power of P4711", {"p": "has_property", "s": P11, "q": {"property": "designShaftPower"}})], [call("get_properties", ids=[P11], requested_properties=["designShaftPower"])],
      ["What is P4711's design shaft power?", "design shaft power of the centrifugal pump?", "The pump that feeds the plate heat exchanger: what is its design shaft power?", "centrif pump shaft power, kW"], [P11])
group("G5", "A route with line numbers and sizes", [F("the route P4711 -> T4750 in order", {"p": "path", "s": P11, "o": T, "q": {"entities": [P11, H7, GV2, T]}}), pipe(P11, H7, "47122", "DN 80"), pipe(H7, GV2, "47123", "DN 80"), pipe(GV2, T, "47123", "DN 80")],
      [call("find_path", source_entity_id=P11, target_entity_id=T)],
      ["Give the route from P4711 to T4750 with line numbers and sizes.", "how does the centrifugal pump's discharge get to the tank? lines and DN please", "P4711 -> T4750: components, lines, DN", "Feed route from the pump on line 47121 to the tank: every item and the size of every pipe."], [P11, T])
group("G6", "A relief device by tag, type and context", [F("set pressure of SV 104.01", prop(SV, "setPressureHigh", "6.0 bar")), F("its inlet comes from the tee on P4712's discharge", {"p": "flows_to", "s": TEE1, "o": SV}, {"p": "relief_device_on_boundary", "s": P12, "o": SV}),
                                                         F("it discharges to T4750", {"p": "flows_to", "s": SV, "o": T}, {"p": "relief_device_on_boundary", "s": T, "o": SV})],
      [PROPS(SV), CONN(SV, "piping")], ["What is the set pressure of SV 104.01, and what is it connected between?", "safety valve: set pressure, where its inlet comes from, where it discharges",
                                         "the relief valve on line 47125: at what pressure is it set and where does it relieve to?", "SV104.01 set pressure + inlet + outlet"], [SV], alt=[ISO(P12), ISO(T)])

# ----- every pattern must be a fact of the graph
problems = 0
OWN = [{"id": p["id"], "gold_calls": g["gold_calls"], "alt_calls": g["alt_calls"], "required": p["required"]} for g in G for p in g["phrasings"] if "required" in p]
for item in [*Q, *G, *OWN]:
    facts = gold_facts(tools, item["gold_calls"])
    wider = gold_facts(tools, [*item["gold_calls"], *item["alt_calls"]])
    for required in item["required"]:
        if "any_of" in required:  # keep only the equivalent forms that some graph operation really produces
            required["any_of"] = [p for p in required["any_of"] if any(matches(p, f) for f in wider)]
            if not required["any_of"]:
                problems += 1; print("NO DERIVABLE FORM:", item["id"], required["fact"])
        patterns = required.get("any_of", [])
        if patterns and not any(matches(patterns[0], f) for f in facts) and not any(matches(p, f) for p in patterns for f in facts):
            problems += 1; print("NOT DERIVED BY GOLD CALLS:", item["id"], required["fact"])
        for pattern in patterns:
            if not any(matches(pattern, f) for f in wider):
                problems += 1; print("PATTERN MATCHES NO GRAPH FACT:", item["id"], required["fact"], pattern)
print(len(Q), "complex questions;", len(G), "groups;", sum(len(g["phrasings"]) for g in G), "phrasings; problems:", problems)
if not problems:
    header = "Follow-up evaluation on C01. Every required item is a canonical fact pattern (or several equivalent ones) produced by a graph operation, or a category the answer must name as not established by the P&ID. tests/test_followup.py re-derives every pattern from the graph."
    json.dump({"description": header, "pid": "data/C01V04-VER.EX01.xml", "questions": Q}, open("evals/followup/complex/questions.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"description": header + " Each group lists phrasings that ask for the same facts; 'required' is the target the group shares and consistency is measured against it. 'anchors' are the items a question names (its input), never items of the answer. A phrasing with its own 'required' is judged for correctness against that: R3a can be read literally as the direct connections of the controller.", "pid": "data/C01V04-VER.EX01.xml", "groups": G}, open("evals/followup/consistency/groups.json", "w"), indent=1, ensure_ascii=False)
