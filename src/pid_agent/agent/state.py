"""Explicit, inspectable agent state and the result returned to callers."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

GroundingStatus = Literal["grounded", "regenerated", "fallback", "not_validated"]


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
    failure_reason: str | None
    usage: dict[str, int]


class AgentResult(BaseModel):
    question_id: str
    question: str
    answer: str
    trace: list[TraceStep]
    evidence: list[dict[str, Any]]
    resolved_entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    grounding_status: GroundingStatus
    claims_checked: int = 0
    unsupported_claims: list[dict[str, Any]] = Field(default_factory=list)
    # Drafts that failed validation and were replaced, with the claims that failed.
    rejected_drafts: list[dict[str, Any]] = Field(default_factory=list)
    limit_reached: str | None = None
    failure_reason: str | None = None
    iterations: int = 0
    usage: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
