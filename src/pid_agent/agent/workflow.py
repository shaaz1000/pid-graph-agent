"""The LangGraph agent: plan -> execute tools -> ... -> answer -> validate -> finalize.

    START -> plan --tool calls--> execute_tools --(budget left)--> plan
                |                      '--(budget spent)--> force_answer
                |--answer--> validate --unsupported, first time--> regenerate -> validate
                |                 '--grounded / still unsupported--> finalize -> END
                '--model failure--> finalize

The model only chooses tools and words the answer. Facts come from GraphTools, every call is
recorded in the trace, and the answer is checked against the collected tool results.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from pid_agent.agent.compact import compact_result, render_evidence
from pid_agent.agent.claims import check_answer
from pid_agent.agent.prompts import (
    FORCED_ANSWER_NOTE,
    MALFORMED_OUTPUT_NOTE,
    REGENERATION_SYSTEM_PROMPT,
    REGENERATION_USER_TEMPLATE,
    SYSTEM_PROMPT,
)
from pid_agent.agent.state import AgentResult, AgentState, TraceStep
from pid_agent.agent.tools import GraphTools, tool_specs
from pid_agent.llm.base import LLMClient, LLMError, LLMResponse, ToolCall, assistant_message

logger = logging.getLogger(__name__)

NO_ANSWER = "I could not determine that from the supplied P&ID graph."
OUT_OF_SCOPE = (
    "I can only answer from the loaded P&ID graph, and no graph-supported statement could be made for this "
    "question. Ask about the equipment, piping, instrumentation or properties in the drawing."
)


@dataclass(frozen=True)
class AgentLimits:
    max_iterations: int = 8       # model planning turns per question
    max_tool_calls: int = 16      # executed tool calls per question
    max_duplicate_calls: int = 2  # identical repeated calls tolerated before forcing an answer
    max_malformed_outputs: int = 2
    # Ask once for a corrected answer when the claims block is missing or incomplete.
    claims_retry: bool = True


class PidAgent:
    def __init__(self, llm: LLMClient, tools: GraphTools, limits: AgentLimits | None = None) -> None:
        self._llm = llm
        self._tools = tools
        self._limits = limits or AgentLimits()
        self._tool_specs = tool_specs()
        self._graph = self._build_graph()

    # ------------------------------------------------------------ public
    def ask(self, question: str, question_id: str | None = None) -> AgentResult:
        started = time.perf_counter()
        question_id = question_id or uuid.uuid4().hex[:8]
        initial: AgentState = {
            "question_id": question_id,
            "question": question,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "pending_calls": [],
            "trace": [],
            "observations": [],
            "resolved_entities": {},
            "iterations": 0,
            "tool_calls_made": 0,
            "duplicate_calls": 0,
            "malformed_streak": 0,
            "limit_reached": None,
            "draft": None,
            "answer": None,
            "unsupported_claims": [],
            "claims_checked": 0,
            "rejected_drafts": [],
            "grounding_attempts": 0,
            "grounding_status": "not_validated",
            "grounding_level": "not_validated",
            "answer_text": None,
            "claims": [],
            "rejected_claims": [],
            "grounding_gaps": [],
            "retry_reasons": [],
            "anchored": False,
            "failure_reason": None,
            "failure_category": None,
            "usage": {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        # Each planning turn takes at most two graph steps; the rest is the answer tail.
        recursion_limit = 2 * self._limits.max_iterations + 2 * self._limits.max_malformed_outputs + 12
        final = self._graph.invoke(initial, config={"recursion_limit": recursion_limit})
        result = AgentResult(
            question_id=question_id,
            question=question,
            answer=final["answer"],
            trace=final["trace"],
            evidence=self._collect_evidence(final["observations"]),
            resolved_entities=final["resolved_entities"],
            grounding_status=final["grounding_status"],
            grounding_level=final["grounding_level"],
            claims=final["claims"],
            rejected_claims=final["rejected_claims"],
            grounding_gaps=final["grounding_gaps"],
            claims_checked=final["claims_checked"],
            unsupported_claims=final["unsupported_claims"],
            rejected_drafts=final["rejected_drafts"],
            limit_reached=final["limit_reached"],
            failure_reason=final["failure_reason"],
            failure_category=final["failure_category"],
            iterations=final["iterations"],
            usage=final["usage"],
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        logger.info(
            "question_done id=%s tools=%s iterations=%d grounding=%s unsupported=%d failure=%s "
            "llm_calls=%d total_tokens=%d duration_ms=%.0f",
            question_id, [s.tool for s in result.trace if s.executed], result.iterations,
            result.grounding_status, len(result.unsupported_claims), result.failure_reason,
            result.usage["llm_calls"], result.usage["total_tokens"], result.duration_ms,
        )
        return result

    # ------------------------------------------------------------- graph
    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("plan", self._plan)
        graph.add_node("execute_tools", self._execute_tools)
        graph.add_node("force_answer", self._force_answer)
        graph.add_node("validate", self._validate)
        graph.add_node("regenerate", self._regenerate)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges("plan", self._after_plan, ["execute_tools", "validate", "plan", "force_answer", "finalize"])
        graph.add_conditional_edges("execute_tools", self._after_tools, ["plan", "force_answer"])
        graph.add_conditional_edges("force_answer", self._after_answer, ["validate", "finalize"])
        graph.add_conditional_edges("validate", self._after_validate, ["regenerate", "finalize"])
        graph.add_conditional_edges("regenerate", self._after_answer, ["validate", "finalize"])
        graph.add_edge("finalize", END)
        return graph.compile()

    # ------------------------------------------------------------- nodes
    def _plan(self, state: AgentState) -> dict[str, Any]:
        """Ask the model for the next tool call(s) or for the answer."""
        first_turn = state["iterations"] == 0
        update: dict[str, Any] = {"iterations": state["iterations"] + 1, "pending_calls": [], "draft": None}
        try:
            # The first turn must consult the graph; afterwards the model decides.
            response = self._llm.complete(state["messages"], self._tool_specs, "required" if first_turn else "auto")
        except LLMError as exc:
            logger.error("llm_failed id=%s error=%s", state["question_id"], exc)
            return {**update, "failure_reason": f"llm_error: {exc}", "failure_category": exc.category}
        update["usage"] = self._add_usage(state["usage"], response)

        if response.tool_calls:
            update["messages"] = [*state["messages"], assistant_message(response)]
            update["pending_calls"] = response.tool_calls
        elif response.malformed_output is None and (response.content or "").strip():
            update["messages"] = [*state["messages"], assistant_message(response)]
            update["draft"] = response.content.strip()
        else:
            detail = "an empty output" if response.malformed_output is None else "output that is not a valid tool call"
            update["malformed_streak"] = state["malformed_streak"] + 1
            update["messages"] = [*state["messages"], {"role": "user", "content": MALFORMED_OUTPUT_NOTE.format(detail=detail)}]
            update["trace"] = [
                *state["trace"],
                TraceStep(
                    step=len(state["trace"]) + 1,
                    tool="(invalid model output)",
                    status="error",
                    result={"message": f"The model produced {detail}; it was asked to try again.", "raw_output": (response.malformed_output or "")[:500]},
                    executed=False,
                ),
            ]
        return update

    def _execute_tools(self, state: AgentState) -> dict[str, Any]:
        """Run the requested graph tools and hand the observations back to the model."""
        messages = list(state["messages"])
        trace = list(state["trace"])
        observations = list(state["observations"])
        resolved = dict(state["resolved_entities"])
        made, duplicates, malformed = state["tool_calls_made"], state["duplicate_calls"], state["malformed_streak"]
        earlier = {self._call_key(s.tool, s.input): s.step for s in trace if s.executed}

        for call in state["pending_calls"]:
            step = len(trace) + 1
            key = self._call_key(call.name, call.arguments)
            if call.parse_error:
                malformed += 1
                payload = {"status": "error", "message": f"Malformed tool call: {call.parse_error}. Send a JSON object matching the tool's schema."}
                trace.append(TraceStep(step=step, tool=call.name, input=None, status="error", result={**payload, "raw_arguments": call.raw_arguments[:500]}, executed=False))
            elif key in earlier:
                duplicates += 1
                payload = {"status": "duplicate", "message": f"This exact call was already made in step {earlier[key]}; its result is above. Use that result, make a different call, or answer."}
                trace.append(TraceStep(step=step, tool=call.name, input=call.arguments, status="duplicate", result=payload, executed=False))
            elif made >= self._limits.max_tool_calls:
                payload = {"status": "error", "message": "Tool call budget for this question is exhausted."}
                trace.append(TraceStep(step=step, tool=call.name, input=call.arguments, status="skipped", result=payload, executed=False))
            else:
                result = self._tools.call(call.name, call.arguments).to_dict()
                made += 1
                malformed = 0
                earlier[key] = step
                observations.append(result)
                payload = self._reuse_note(result, resolved) or compact_result(result)
                self._remember(result, resolved, step)
                trace.append(TraceStep(step=step, tool=call.name, input=call.arguments, status=result["status"], result=payload, duration_ms=result["meta"].get("duration_ms", 0.0)))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(payload, ensure_ascii=False)})

        return {"messages": messages, "trace": trace, "observations": observations, "resolved_entities": resolved, "pending_calls": [], "tool_calls_made": made, "duplicate_calls": duplicates, "malformed_streak": malformed}

    def _force_answer(self, state: AgentState) -> dict[str, Any]:
        """A budget is spent: require an answer from what has been collected, without tools."""
        reason = self._limit_reason(state) or "step limit reached"
        messages = [*state["messages"], {"role": "user", "content": FORCED_ANSWER_NOTE.format(reason=reason)}]
        update: dict[str, Any] = {"limit_reached": reason, "messages": messages, "draft": None}
        try:
            response = self._llm.complete(messages, self._tool_specs, "none")
        except LLMError as exc:
            return {**update, "failure_reason": f"llm_error: {exc}", "failure_category": exc.category}
        update["usage"] = self._add_usage(state["usage"], response)
        if (response.content or "").strip() and not response.tool_calls:
            update["draft"] = response.content.strip()
        else:
            update["failure_reason"] = f"no_answer_generated: {reason}"
        return update

    def _validate(self, state: AgentState) -> dict[str, Any]:
        """Deterministic claim-to-evidence validation of the draft. No model is involved."""
        report = check_answer(state["draft"] or "", state["question"], state["observations"], SYSTEM_PROMPT)
        # Unsupported content always triggers the one rewrite; missing or incomplete claims do
        # so only on the first attempt, after which the answer is at most "limited".
        soft = report.gaps if self._limits.claims_retry and state["grounding_attempts"] == 0 else []
        reasons = [*report.problems, *soft]
        if reasons:
            logger.warning("grounding_failed id=%s attempt=%d unsupported=%s", state["question_id"], state["grounding_attempts"], [c["claim"] for c in reasons])
        update: dict[str, Any] = {
            "unsupported_claims": report.problems, "claims_checked": report.checked, "claims": report.supported,
            "rejected_claims": report.rejected, "grounding_gaps": report.gaps, "grounding_level": report.level,
            "answer_text": report.answer, "anchored": report.anchored, "retry_reasons": reasons,
        }  # fmt: skip
        if reasons:
            update["rejected_drafts"] = [*state["rejected_drafts"], {"draft": state["draft"], "unsupported_claims": reasons}]
        return update

    def _regenerate(self, state: AgentState) -> dict[str, Any]:
        """One constrained rewrite from evidence only."""
        evidence = "\n".join(
            f"[{step.step}] {step.tool}({json.dumps(step.input, ensure_ascii=False)}) -> {json.dumps(step.result, ensure_ascii=False)}"
            for step in state["trace"] if step.executed
        ) or "(no tool results were collected)"
        claims = "\n".join(f"- {c['claim']}: {c['reason']}" for c in state["retry_reasons"])
        messages = [
            {"role": "system", "content": REGENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": REGENERATION_USER_TEMPLATE.format(question=state["question"], evidence=evidence, draft=state["draft"], claims=claims)},
        ]
        update: dict[str, Any] = {"grounding_attempts": state["grounding_attempts"] + 1}
        try:
            response = self._llm.complete(messages, None, "none")
        except LLMError as exc:
            return {**update, "failure_reason": f"llm_error: {exc}", "failure_category": exc.category, "draft": None}
        update["usage"] = self._add_usage(state["usage"], response)
        text = (response.content or "").strip()
        if not text:
            return {**update, "failure_reason": "no_answer_generated: empty regeneration", "draft": None}
        return {**update, "draft": text}

    def _finalize(self, state: AgentState) -> dict[str, Any]:
        draft, unsupported = state["draft"], state["unsupported_claims"]
        if draft and not unsupported and state["anchored"]:
            status = "regenerated" if state["grounding_attempts"] else "grounded"
            return {"answer": state["answer_text"] or draft, "grounding_status": status}
        # Fail closed: nothing the model wrote is shown, and no claim is reported as supported.
        level = "insufficient_evidence" if draft else "not_validated"
        return {"answer": self._fallback_answer(state), "grounding_status": "fallback", "grounding_level": level, "claims": []}

    # ----------------------------------------------------------- routing
    def _limit_reason(self, state: AgentState) -> str | None:
        limits = self._limits
        if state["duplicate_calls"] >= limits.max_duplicate_calls:
            return "the same tool call was repeated"
        if state["malformed_streak"] >= limits.max_malformed_outputs:
            return "repeated malformed tool calls"
        if state["tool_calls_made"] >= limits.max_tool_calls:
            return f"the limit of {limits.max_tool_calls} tool calls was reached"
        if state["iterations"] >= limits.max_iterations:
            return f"the limit of {limits.max_iterations} planning steps was reached"
        return None

    def _after_plan(self, state: AgentState) -> str:
        if state["failure_reason"]:
            return "finalize"
        if state["pending_calls"]:
            return "execute_tools"
        if state["draft"]:
            return "validate"
        return "force_answer" if self._limit_reason(state) else "plan"

    def _after_tools(self, state: AgentState) -> str:
        return "force_answer" if self._limit_reason(state) else "plan"

    @staticmethod
    def _after_answer(state: AgentState) -> str:
        return "validate" if state["draft"] else "finalize"

    @staticmethod
    def _after_validate(state: AgentState) -> str:
        if state["retry_reasons"] and state["grounding_attempts"] == 0:
            return "regenerate"
        return "finalize"

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _call_key(name: str, arguments: dict[str, Any] | None) -> str:
        cleaned = {k: v for k, v in (arguments or {}).items() if v is not None}
        return f"{name}:{json.dumps(cleaned, sort_keys=True, default=str)}"

    @staticmethod
    def _remember(result: dict[str, Any], resolved: dict[str, dict[str, Any]], step: int) -> None:
        """Keep every entity the tools have identified, so it need not be looked up again."""
        for entity in result.get("entities", []):
            if "id" in entity and "type" in entity:
                resolved.setdefault(entity["id"], {"name": entity.get("name", entity["id"]), "type": entity["type"], "step": step})

    @staticmethod
    def _reuse_note(result: dict[str, Any], resolved: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        """A lookup that only re-finds a known entity gets a short reminder instead of a full result."""
        if result["tool"] != "find_entities" or result["status"] != "success" or len(result["entities"]) != 1:
            return None
        known = resolved.get(result["entities"][0]["id"])
        if known is None:
            return None
        entity = result["entities"][0]
        return {
            "status": "success",
            "entities": [{"id": entity["id"], "name": entity["name"], "type": entity["type"]}],
            "note": f"{entity['id']} was already identified in step {known['step']}. Use this id directly in other tools.",
            **({"warnings": result["warnings"]} if result.get("warnings") else {}),
        }

    @staticmethod
    def _add_usage(usage: dict[str, int], response: LLMResponse) -> dict[str, int]:
        total = dict(usage)
        total["llm_calls"] += 1
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            total[key] += response.usage.get(key, 0)
        return total

    @staticmethod
    def _collect_evidence(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence: dict[tuple[str, str], dict[str, Any]] = {}
        for result in observations:
            for item in result.get("evidence", []):
                evidence.setdefault((item["kind"], item["id"]), item)
        return list(evidence.values())

    @staticmethod
    def _fallback_answer(state: AgentState) -> str:
        """A cautious answer assembled directly from structured evidence, with no model text."""
        failure, unsupported = state["failure_reason"], state["unsupported_claims"]
        if failure and failure.startswith("llm_error"):
            head = (
                "I could not answer this question because the language model provider call failed "
                f"({state['failure_category']}: {failure.split(': ', 1)[1]}). This is an infrastructure "
                "failure, not a statement about the P&ID."
            )
        elif unsupported:
            head = f"{NO_ANSWER} A drafted answer was withheld because {len(unsupported)} of its claims were not supported by the graph evidence."
        elif state["draft"]:
            head = OUT_OF_SCOPE
        else:
            head = f"{NO_ANSWER} The model did not produce a usable answer."
        lines = render_evidence(state["observations"])
        if not lines:
            return f"{head} No graph evidence was collected."
        return head + "\n\nWhat the graph tools returned:\n" + "\n".join(f"- {line}" for line in lines)


def format_transcript(result: AgentResult, show_results: bool = True) -> str:
    """Human-readable record of what was actually executed. Contains no model reasoning."""
    out = [f"QUESTION [{result.question_id}]", result.question, ""]
    for step in result.trace:
        out.append(f"STEP {step.step}")
        out.append(f"Tool:   {step.tool}" + ("" if step.executed else "   (not executed)"))
        if step.input is not None:
            out.append(f"Input:  {json.dumps(step.input, ensure_ascii=False)}")
        out.append(f"Status: {step.status}")
        if show_results:
            out.append("Result: " + json.dumps(step.result, ensure_ascii=False, indent=2))
        out.append("")
    out += ["FINAL ANSWER", result.answer, ""]
    out.append(f"GROUNDING: {result.grounding_status} ({result.claims_checked} plant-specific claims checked, {len(result.unsupported_claims)} unsupported)")
    out.append(f"GROUNDING LEVEL: {result.grounding_level}")
    for item in result.claims:
        out.append(f"  supported claim: {item['text']}")
        for fact in item["facts"]:
            out.append(f"      <- {fact['id']} {fact['predicate']} [{fact.get('evidence_id', '')}] {fact.get('source_graph', '')}: {', '.join(fact.get('source_object_ids', []))}")
    for gap in result.grounding_gaps:
        out.append(f"  token-level only: {gap['claim']} ({gap['reason']})")
    for claim in result.unsupported_claims:
        out.append(f"  unsupported: {claim['claim']} ({claim['reason']})")
    for rejected in result.rejected_drafts:
        claims = ", ".join(c["claim"] for c in rejected["unsupported_claims"])
        out.append(f"  a draft was rejected for unsupported claims: {claims}")
    if result.limit_reached:
        out.append(f"LIMIT REACHED: {result.limit_reached}")
    if result.failure_reason:
        kind = f" [infrastructure: {result.failure_category}]" if result.failure_category else ""
        out.append(f"FAILURE{kind}: {result.failure_reason}")
    out.append("")
    out.append(f"EVIDENCE ({len(result.evidence)} graph facts)")
    for item in result.evidence:
        out.append(f"  [{item['kind']}] {item['id']}  <- {item['source_graph']}: {', '.join(item['source_object_ids'])}")
    usage = result.usage
    out += ["", f"USAGE: {usage.get('llm_calls', 0)} model calls, {usage.get('total_tokens', 0)} tokens, {result.duration_ms:.0f} ms"]
    return "\n".join(out)
