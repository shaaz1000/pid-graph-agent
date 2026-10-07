"""Builds the holdout set: fresh questions, gold derived from the graph before any inference.

Every fact pattern is checked against the graph, as in ../build_gold.py. Run from the project root.
"""
import json
import sys

sys.path.insert(0, "evals/followup")
from followup import gold_facts, matches  # noqa: E402

from pid_agent.agent.tools import GraphTools  # noqa: E402
from pid_agent.graph.service import GraphService  # noqa: E402

tools = GraphTools(GraphService.from_file("data/C01V04-VER.EX01.xml"))
T, P12, P11, H7, H8 = "Tank-1", "ReciprocatingPump-1", "CentrifugalPump-1", "PlateHeatExchanger-1", "TubularHeatExchanger-1"
SV, BFV, CHK, RED, BV1, BV3, BV4, BF1 = "SpringLoadedGlobeSafetyValve-1", "ButterflyValve-1", "SwingCheckValve-1", "PipeReducer-1", "BallValve-1", "BallValve-3", "BallValve-4", "BlindFlange-1"
PIF1, PSG1 = "ProcessInstrumentationFunction-1", "ProcessSignalGeneratingFunction-1"
TEE1, TEE2, TEE3, TEE4, TEE5, FOUT = "PipeTee-1", "PipeTee-2", "PipeTee-3", "PipeTee-4", "PipeTee-5", "FlowOutPipeOffPageConnector-1"


def call(tool, **args): return {"tool": tool, "args": args}
def F(label, *patterns): return {"fact": label, "any_of": list(patterns)}
def U(*categories): return {"unknown": list(categories)}
def prop(e, name, value): return {"p": "has_property", "s": e, "v": value, "q": {"property": name}}
def reach(a, b, direction): return {"p": "reaches", "s": a, "o": b, "q": {"direction": direction}}


BOXED = [F("BallValve 47124/C4 is the shut-off valve on the downstream side", {"p": "isolation_boundary_valve", "s": RED, "o": BV1}, {"p": "flows_to", "s": RED, "o": BV1}),
         F("the valve on the upstream side is a check valve, not a shut-off valve", {"p": "check_valve_on_boundary", "s": RED, "o": CHK}, {"p": "is_a", "s": CHK, "v": "SwingCheckValve"})]
CUT_OFF = [F("no drawn route from T4750 to P4712 with the butterfly valve treated as closed", {"p": "no_path", "ends": [T, P12], "blocked_contains": BFV})]
TAPPED = [F("the measurement is taken at BlindFlange 47126/C6", {"p": "senses_at", "s": PSG1, "o": BF1}, {"p": "loop_measured_at", "s": PIF1, "o": BF1}, {"p": "signal_chain", "contains": [PSG1, BF1]}),
          F("PT4712.01 feeds PI4712.01", {"p": "measurement_input_to", "s": PSG1, "o": PIF1}, {"p": "signal_chain", "contains": [PSG1, PIF1]})]

Q = []


def add(id, pattern, question, calls, required, alt=(), anchors=(), partial="", forbidden_conclusions=()):
    Q.append({"id": id, "source": "holdout", "type": pattern, "question": question, "anchors": list(anchors), "gold_calls": list(calls), "alt_calls": list(alt), "required": required,
              "acceptable_partial": partial, "forbidden_conclusions": list(forbidden_conclusions)})


add("H1", "Isolation boundary with an unresolved gap", "The reducer in the suction piping of the reciprocating pump has to be replaced. Which valves box it in on each side, and is each side closed off by a shut-off valve?",
    [call("isolation_boundary", entity_id=RED)], BOXED, alt=[call("get_connections", entity_id=RED, relationship="piping"), call("find_entities", query="check valve")], anchors=[RED],
    partial="Naming both neighbouring valves without saying that one is a check valve.", forbidden_conclusions=["that the reducer can be positively isolated on both sides", "a sequence for closing the valves"])
add("H2", "Path comparison", "From P4712, compare the way to the off-page outlet with the way to H1008: list what lies on each, and name the last item the two routes have in common.",
    [call("find_path", source_entity_id=P12, target_entity_id=FOUT), call("find_path", source_entity_id=P12, target_entity_id=H8)],
    [F("the route P4712 -> off-page outlet", {"p": "path", "s": P12, "o": FOUT, "q": {"entities": [P12, TEE2, TEE1, TEE3, BV4, TEE4, TEE5, FOUT]}}),
     F("the route P4712 -> H1008", {"p": "path", "s": P12, "o": H8, "q": {"entities": [P12, TEE2, TEE1, TEE3, BV4, TEE4, H8]}})], anchors=[P12, H8],
    partial="One of the two routes.", forbidden_conclusions=["where the piping goes beyond the off-page connector", "which route carries more flow"])
add("H3", "Instrumentation chain with piping context", "For PI4712.01: where on the piping is its measurement tapped, which transmitter feeds it, what size is the branch at the tap point, and does this indication drive any valve?",
    [call("trace_instrumentation", entity_id=PIF1), call("get_properties", ids=[BF1], requested_properties=["nominalDiameterRepresentation"])],
    [*TAPPED, F("the branch at the tap point is DN 25", prop(BF1, "nominalDiameterRepresentation", "DN 25"), {"p": "flows_to", "s": BV3, "o": BF1, "q": {"nominalDiameterRepresentation": "DN 25"}}, {"p": "line_run", "o": BF1, "q": {"diameters": ["DN 25"]}}),
     F("the chain ends at the indication: no actuating function or operated valve follows it", {"p": "signal_chain", "s": BF1, "o": PIF1}, {"unknown_ok": True})],
    alt=[call("get_connections", entity_id=BF1, relationship="piping"), call("trace_line", line="47126")], anchors=[PIF1],
    partial="The tap point and transmitter without the branch size.", forbidden_conclusions=["an operated valve for this indication", "the pressure the indicator shows"])
add("H4", "Branch-aware line tracing", "Trace line 47125 from end to end: where it starts, what sits on it, where it ends, and how its size changes along the way.",
    [call("trace_line", line="47125")],
    [F("it starts at the tee PipeTee 47126/C3 and passes SV 104.01", {"p": "line_run", "s": TEE1, "contains": [SV]}, {"p": "flows_to", "s": TEE1, "o": SV}),
     F("it ends at T4750", {"p": "line_run", "s": TEE1, "o": T}, {"p": "flows_to", "s": SV, "o": T}),
     F("DN 25 before the safety valve", {"p": "line_run", "s": TEE1, "o": T, "q": {"diameters": ["DN 25", "DN 50"]}}, {"p": "flows_to", "s": TEE1, "o": SV, "q": {"nominalDiameterRepresentation": "DN 25"}}),
     F("DN 50 after the safety valve", {"p": "line_run", "s": TEE1, "o": T, "q": {"diameters": ["DN 25", "DN 50"]}}, {"p": "flows_to", "s": SV, "o": T, "q": {"nominalDiameterRepresentation": "DN 50"}})],
    alt=[call("get_connections", entity_id=SV, relationship="piping")], partial="Start and end without both sizes.", forbidden_conclusions=["when the safety valve lifts", "that the line is normally empty or normally flowing"])
add("H5", "Reachability with a component closed", "With the butterfly valve at the tank outlet closed, is there still a drawn route from T4750 to P4712? State which line that valve is on.",
    [call("find_path", source_entity_id=T, target_entity_id=P12, blocked_entity_ids=[BFV]), call("get_properties", ids=[BFV], requested_properties=["lineNumber"])],
    [*CUT_OFF, F("the butterfly valve is on line 47124", prop(BFV, "lineNumber", "47124"), {"p": "flows_to", "s": T, "o": BFV, "q": {"lineNumber": "47124"}}, {"p": "isolation_boundary_valve", "o": BFV, "q": {"line": "47124"}})],
    alt=[call("find_path", source_entity_id=P12, target_entity_id=T, direction="upstream", blocked_entity_ids=[BFV]), call("get_connections", entity_id=T, relationship="piping"), call("isolation_boundary", entity_id=T)], anchors=[BFV],
    partial="The missing route without the line.", forbidden_conclusions=["that the pump runs dry, cavitates or trips", "that flow stops"])
add("H6", "Inventory filtered by two attributes", "Which ball valves are both on line 47126 and on DN 50 piping?",
    [call("list_entities", entity_type="BallValve", properties=["lineNumber", "nominalDiameterRepresentation"], property_filter={"lineNumber": "47126", "nominalDiameterRepresentation": "DN 50"})],
    [F("BallValve 47126/C7 is on line 47126", prop(BV4, "lineNumber", "47126")), F("BallValve 47126/C7 is on DN 50 piping", prop(BV4, "nominalDiameterRepresentation", "DN 50"))],
    partial="The valve with one of the two attributes.", forbidden_conclusions=["a function or purpose for the valve"])
add("H7", "Downstream reach with recycle", "List the equipment downstream of the plate heat exchanger, and say whether the piping comes back around to any of it.",
    [call("traverse", start_entity_id=H7, direction="downstream", entity_types=["equipment"]), call("traverse", start_entity_id=P12, direction="downstream", entity_types=["equipment"])],
    [F("T4750 is downstream of H1007", reach(H7, T, "downstream"), {"p": "path", "s": H7, "o": T}), F("P4712 is downstream of H1007", reach(H7, P12, "downstream"), {"p": "path", "s": H7, "o": P12}),
     F("H1008 is downstream of H1007", reach(H7, H8, "downstream"), {"p": "path", "s": H7, "o": H8}),
     F("the piping returns to T4750 from further downstream", reach(P12, T, "downstream"), reach(H8, T, "downstream"), {"p": "path", "s": P12, "o": T}, {"p": "path", "s": H8, "o": T})],
    alt=[call("traverse", start_entity_id=H8, direction="downstream", entity_types=["equipment"]), call("find_path", source_entity_id=H7, target_entity_id=T), call("find_path", source_entity_id=H7, target_entity_id=P12),
         call("find_path", source_entity_id=H7, target_entity_id=H8), call("find_path", source_entity_id=P12, target_entity_id=T), call("find_path", source_entity_id=H8, target_entity_id=T)], anchors=[H7],
    partial="The downstream equipment without the return.", forbidden_conclusions=["flow rates or a recycle ratio", "that the loop is in operation"])
add("H8", "Relief-device position", "Standing at SV 104.01: which equipment is piped to it with no shut-off valve in between, on its inlet side and on its outlet side, and what is it there to protect?",
    [call("isolation_boundary", entity_id=SV)],
    [F("P4712 is piped to its inlet side with no shut-off valve between", {"p": "unisolated_connection", "s": SV, "o": P12}, {"p": "relief_device_on_boundary", "s": P12, "o": SV}),
     F("T4750 is piped to its outlet side with no shut-off valve between", {"p": "unisolated_connection", "s": SV, "o": T}, {"p": "flows_to", "s": SV, "o": T}, {"p": "relief_device_on_boundary", "s": T, "o": SV}), U("purpose_or_intent")],
    alt=[call("isolation_boundary", entity_id=P12), call("isolation_boundary", entity_id=T), call("get_connections", entity_id=SV, relationship="piping")], anchors=[SV],
    partial="Both pieces of equipment without the unknown.", forbidden_conclusions=["what the valve protects against, stated as a fact", "that the relief capacity is adequate"])

G = []


def group(id, title, based_on, required, calls, phrasings, anchors, alt=()):
    G.append({"id": id, "title": title, "source": "holdout", "complex": True, "based_on": based_on, "anchors": list(anchors), "gold_calls": list(calls), "alt_calls": list(alt), "required": required,
              "phrasings": [{"id": f"{id}{chr(97 + i)}", "style": style, "question": q} for i, (style, q) in enumerate(phrasings)]})


group("HG1", "Valves around a fitting", "H1", BOXED, [call("isolation_boundary", entity_id=RED)],
      [("exact identifier", "PipeReducer 47124/C3: which valves bound it on each side, and is each of them a shut-off valve?"),
       ("type description", "The pipe reducer on this sheet is to be swapped out. What valves box it in, and are they all isolation valves?"),
       ("property and context", "Where the suction pipe of P4712 steps down from DN 80 to DN 50, which valves sit either side of that fitting, and can both be shut?"),
       ("terse operator wording", "47124 C3 reducer: bounding valves, shut-off or not?")],
      [RED], alt=[call("get_connections", entity_id=RED, relationship="piping"), call("find_entities", query="check valve")])
group("HG2", "A route with one valve closed", "H5", CUT_OFF, [call("find_path", source_entity_id=T, target_entity_id=P12, blocked_entity_ids=[BFV])],
      [("exact identifier", "With ButterflyValve 47124/C1 closed, is there still a drawn route from T4750 to P4712?"),
       ("type description", "Shut the butterfly valve. Is the reciprocating pump still connected to the tank on its suction side?"),
       ("property and context", "Suppose the DN 80 valve directly on the tank's outlet is closed: does any drawn path remain from the tank to the pump with the 40 m design pressure head?"),
       ("terse operator wording", "47124/C1 shut: T-4750 to P-4712 still connected?")],
      [BFV], alt=[call("find_path", source_entity_id=P12, target_entity_id=T, direction="upstream", blocked_entity_ids=[BFV])])
group("HG3", "An indication and where it is tapped", "H3", TAPPED, [call("trace_instrumentation", entity_id=PIF1)],
      [("exact identifier", "PI4712.01: at which component is its measurement taken, and which transmitter feeds it?"),
       ("type description", "The pressure indication that is located in the field: what does it read from, and at which point on the piping?"),
       ("property and context", "Which transmitter measures at the blind flange behind valve 47126/C5, and which indication does it feed?"),
       ("terse operator wording", "PI 4712.01: tap point + source transmitter")],
      [], alt=[call("trace_instrumentation", entity_id=BF1)])

problems = 0
for item in [*Q, *G]:
    facts = gold_facts(tools, item["gold_calls"])
    wider = gold_facts(tools, [*item["gold_calls"], *item["alt_calls"]])
    for required in item["required"]:
        if "any_of" in required:
            if any("unknown_ok" in p for p in required["any_of"]):  # the absence may also be stated as an unknown
                required["any_of"] = [p for p in required["any_of"] if "unknown_ok" not in p]
                required["unknown"] = ["not_represented"]
            for pattern in required["any_of"]:
                if not any(matches(pattern, f) for f in wider):
                    problems += 1
                    print("PATTERN MATCHES NO GRAPH FACT:", item["id"], required["fact"], pattern)
            if not any(matches(p, f) for p in required["any_of"] for f in facts):
                problems += 1
                print("NOT DERIVED BY GOLD CALLS:", item["id"], required["fact"])
print(len(Q), "holdout questions;", len(G), "groups;", sum(len(g["phrasings"]) for g in G), "phrasings; problems:", problems)
if not problems:
    note = "Holdout sanity check on C01, written after the formal follow-up evaluation and frozen before any model call. Gold is derived from the graph by build_holdout.py. Not part of the official follow-up scores."
    json.dump({"description": note, "pid": "data/C01V04-VER.EX01.xml", "questions": Q}, open("evals/followup/holdout/questions.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"description": note, "pid": "data/C01V04-VER.EX01.xml", "groups": G}, open("evals/followup/holdout/groups.json", "w"), indent=1, ensure_ascii=False)
