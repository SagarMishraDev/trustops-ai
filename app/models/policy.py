"""Policy and EvidenceRecord models (Phase 4).

Policy: a business rule the chatbot must follow. Policies belong to ONE
business, can be enabled/disabled, and every issue they trigger records
the policy id + title snapshot - even if the policy is later deleted,
the historical evaluation still shows WHICH rule fired.

EvidenceRecord: a company-provided fact (reference answer, approved
action, business record note). Evaluations check claims against these
records. A claim is only ever 'verified' when a record actually
supports it - the records are the evidence, not the model's opinion.
"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "refund R-123", "order 456 status"
    content: Mapped[str] = mapped_column(Text, nullable=False)  # the fact itself
    source: Mapped[str] = mapped_column(String(100), default="manual")  # manual | document | integration
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
