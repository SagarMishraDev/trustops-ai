"""HumanReview model.

Human decisions live in their OWN table. The Evaluation row is never
edited by a reviewer - if a human disagrees with the AI, both records
exist and the disagreement itself becomes measurable data (false-positive
rate in Phase 6)."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"), index=True, nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)  # confirmed | false_positive
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
