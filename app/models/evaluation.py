"""Evaluation + EvaluationIssue models.

An Evaluation is the system's judgment on ONE conversation. The record is
immutable once written - human review decisions (Phase 5) will live in a
separate table so the original AI judgment is never overwritten.
"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100, computed deterministically
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # passed | flagged | needs_review
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)  # low | medium | high | critical
    evidence_assessment: Mapped[str] = mapped_column(String(30), default="unverified")
    # verified | unsupported | unverified | contradicted | insufficient_evidence
    prompt_injection_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluation_model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation = relationship("Conversation")
    issues = relationship("EvaluationIssue", back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationIssue(Base):
    __tablename__ = "evaluation_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # low | medium | high | critical
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="deterministic")  # deterministic | llm | mock
    policy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # snapshot, survives policy deletion
    policy_title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    evaluation = relationship("Evaluation", back_populates="issues")
