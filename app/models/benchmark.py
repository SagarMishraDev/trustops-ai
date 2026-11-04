"""BenchmarkRun + PromptVersion models (Phase 6).

A BenchmarkRun is one measured pass over the labeled dataset. Metrics are
computed from actual engine outputs - a run that scores badly is stored
just as faithfully as a good one.
"""
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluation_model: Mapped[str] = mapped_column(String(100), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    true_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False)
    true_negatives: Mapped[int] = mapped_column(Integer, nullable=False)
    false_negatives: Mapped[int] = mapped_column(Integer, nullable=False)
    precision: Mapped[float] = mapped_column(Float, nullable=False)
    recall: Mapped[float] = mapped_column(Float, nullable=False)
    f1_score: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    category_detection_rate: Mapped[float] = mapped_column(Float, default=0.0)
    average_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[str] = mapped_column(Text, default="[]")  # per-case JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
