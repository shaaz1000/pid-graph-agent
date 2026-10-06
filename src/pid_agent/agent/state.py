"""Explicit, inspectable agent state and the result returned to callers."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

GroundingStatus = Literal["grounded", "regenerated", "fallback", "not_validated"]
# What the deterministic validation established about the final answer. Not a model confidence.
GroundingLevel = Literal["grounded", "limited", "ambiguous", "insufficient_evidence", "not_validated"]


class TraceStep(BaseModel):
    """One actual tool execution (or a rejected model output). Not model reasoning."""

    step: int
    tool: str
    input: dict[str, Any] | None = None
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    executed: bool = True


class AgentState(TypedDict, total=False):
    question_id: str
    question: str
    messages: list[dict[str, Any]]
    pending_calls: list[Any]
    trace: list[TraceStep]
    observations: list[dict[str, Any]]  # full tool results, used for grounding
    resolved_entities: dict[str, dict[str, Any]]  # id -> name/type/first step, for reuse
    iterations: int
    tool_calls_made: int
    duplicate_calls: int
    malformed_streak: int
    limit_reached: str | None
    draft: str | None
    answer: str | None
    unsupported_claims: list[dict[str, Any]]
    claims_checked: int
    rejected_drafts: list[dict[str, Any]]
    grounding_attempts: int
    grounding_status: GroundingStatus
    grounding_level: GroundingLevel
    answer_text: str | None  # the draft without its claims block
    claims: list[dict[str, Any]]  # structured claims that typed facts support, with those facts
    rejected_claims: list[dict[str, Any]]
    grounding_gaps: list[dict[str, Any]]  # text that passed only the token-level check
    retry_reasons: list[dict[str, Any]]
    anchored: bool
    truncated_outputs: int
    failure_reason: str | None
    failure_category: str | None
    usage: dict[str, int]
    submission: dict[str, Any] | None  # the validated structured answer, when that contract is used
    submission_attempts: int
    requested_outputs: list[dict[str, Any]] | None  # what the question asks for, recorded first
    decompose_attempts: int
    repair: dict[str, Any] | None  # the one repair of a rejected final submission


class AgentResult(BaseModel):
    question_id: str
    question: str
    answer: str
    trace: list[TraceStep]
    evidence: list[dict[str, Any]]
    resolved_entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    grounding_status: GroundingStatus
    grounding_level: GroundingLevel = "not_validated"
    # Each supported claim with the typed facts (and their graph provenance) that entail it.
    claims: list[dict[str, Any]] = Field(default_factory=list)
    rejected_claims: list[dict[str, Any]] = Field(default_factory=list)
    grounding_gaps: list[dict[str, Any]] = Field(default_factory=list)
    # Model outputs that hit the output-token limit (finish_reason=length) and were discarded.
    truncated_outputs: int = 0
    claims_checked: int = 0
    unsupported_claims: list[dict[str, Any]] = Field(default_factory=list)
    # Drafts that failed validation and were replaced, with the claims that failed.
    rejected_drafts: list[dict[str, Any]] = Field(default_factory=list)
    limit_reached: str | None = None
    failure_reason: str | None = None
    # Set for infrastructure failures (rate_limit, authentication, ...): the question was not
    # answered because the model could not be reached, not because of anything in the graph.
    failure_category: str | None = None
    iterations: int = 0
    usage: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0.0
    # "structured": the model called submit_answer and the application wrote the answer from
    # the cited evidence. "prose": the model wrote text with evidence ids (the original contract).
    answer_mode: str = "prose"
    # Structured answers only: direct facts, derived facts and unknowns as validated, each
    # cited row with its canonical facts.
    submission: dict[str, Any] | None = None
    # Structured answers only: what the question asks for (q1, q2, ...), recorded before any lookup.
    requested_outputs: list[dict[str, Any]] | None = None
    # Structured answers only: set when the final submission was rejected and the model was given
    # its one chance to repair it. {"initial_problems": [...], "attempted": true, "succeeded": bool}
    repair: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
