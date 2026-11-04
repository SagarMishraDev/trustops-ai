"""Business (tenant) model.

A business is the customer of TrustOps. Every conversation, policy and
evaluation belongs to exactly one business - that is how data isolation
is enforced. The plain API key is NEVER stored, only its SHA-256 hash.
"""
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversations = relationship("Conversation", back_populates="business", cascade="all, delete-orphan")
