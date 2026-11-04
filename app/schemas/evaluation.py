"""Structured evaluation output schemas.

This is the CONTRACT for the evaluation engine. Whether the judgment comes
from deterministic Python, the mock evaluator, or a real LLM, it must be
validated into exactly this shape before anything is saved or returned.
An LLM that returns free text instead of this structure is rejected, not
trusted - invalid output never reaches the database as an evaluation.
"""
from typing import Literal
from pydantic import BaseModel, Field

Category = Literal[
    "relevance", "accuracy", "hallucination", "policy_violation",
    "context_consistency", "completeness", "clarity", "sensitive_information",
]
Severity = Literal["low", "medium", "high", "critical"]


class IssueSchema(BaseModel):
    category: Category
    severity: Severity
    reason: str
    evidence: str | None = None
    suggested_action: str | None = None
    source: str = "llm"
    policy_id: int | None = None
    policy_title: str | None = None


class EvaluationResultSchema(BaseModel):
    """What an evaluator (mock or LLM) returns - before scoring/persistence."""
    issues: list[IssueSchema] = Field(default_factory=list)
    evidence_assessment: Literal[
        "verified", "unsupported", "unverified", "contradicted", "insufficient_evidence"
    ] = "unverified"
    suggested_reply: str | None = None


class EvaluationRequest(BaseModel):
    conversation_id: int  # internal DB id from Phase 2
    policies: list[str] = Field(default_factory=list)  # policy rule texts; DB policies arrive in Phase 4
    evidence: str | None = None  # supporting evidence text, if the business has any


class BulkEvaluationRequest(BaseModel):
    conversation_ids: list[int] | None = None  # None = all of this business's conversations (max 200)
    policies: list[str] = Field(default_factory=list)


class IssueOut(BaseModel):
    category: str
    severity: str
    reason: str
    evidence: str | None
    suggested_action: str | None
    source: str
    policy_id: int | None = None
    policy_title: str | None = None


class EvaluationOut(BaseModel):
    id: int
    conversation_id: int
    conversation_external_id: str
    status: str
    overall_score: int
    risk_level: str
    evidence_assessment: str
    prompt_injection_detected: bool
    issues: list[IssueOut]
    suggested_reply: str | None
    human_review_required: bool
    evaluation_model: str
    prompt_version: str
    latency_ms: int
    estimated_cost: float

    @classmethod
    def from_model(cls, ev) -> "EvaluationOut":
        return cls(
            id=ev.id, conversation_id=ev.conversation_id,
            conversation_external_id=ev.conversation.external_conversation_id,
            status=ev.status, overall_score=ev.overall_score, risk_level=ev.risk_level,
            evidence_assessment=ev.evidence_assessment,
            prompt_injection_detected=ev.prompt_injection_detected,
            issues=[IssueOut(category=i.category, severity=i.severity, reason=i.reason,
                             evidence=i.evidence, suggested_action=i.suggested_action, source=i.source,
                             policy_id=i.policy_id, policy_title=i.policy_title)
                    for i in ev.issues],
            suggested_reply=ev.suggested_reply, human_review_required=ev.human_review_required,
            evaluation_model=ev.evaluation_model, prompt_version=ev.prompt_version,
            latency_ms=ev.latency_ms, estimated_cost=ev.estimated_cost,
        )
