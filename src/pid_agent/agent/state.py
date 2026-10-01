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
    failure_reason: str | None
    failure_category: str | None
    usage: dict[str, int]


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

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
