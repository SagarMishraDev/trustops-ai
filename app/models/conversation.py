"""Conversation model - one user message + one assistant response.

external_conversation_id is the ID from the customer's own chatbot system.
(business_id, external_conversation_id) is UNIQUE together: that single
constraint is what makes duplicate imports and webhook retries safe -
the database itself refuses a second copy.
"""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("business_id", "external_conversation_id", name="uq_business_external_conversation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    external_conversation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_response: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="api")  # csv | json | api | webhook
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    business = relationship("Business", back_populates="conversations")
