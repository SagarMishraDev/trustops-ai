from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    decision: Literal["confirmed", "false_positive"]
    reviewer_name: str = Field(min_length=1, max_length=100)
    notes: str | None = None


class ReviewOut(BaseModel):
    id: int
    evaluation_id: int
    reviewer_name: str
    decision: str
    notes: str | None
    reviewed_at: datetime

    @classmethod
    def from_model(cls, r) -> "ReviewOut":
        return cls(id=r.id, evaluation_id=r.evaluation_id, reviewer_name=r.reviewer_name,
                   decision=r.decision, notes=r.notes, reviewed_at=r.reviewed_at)
