import json
from pydantic import BaseModel, Field


class PromptVersionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    prompt_content: str = Field(min_length=10)


class PromptVersionOut(BaseModel):
    id: int
    name: str
    version: str
    prompt_content: str

    @classmethod
    def from_model(cls, p) -> "PromptVersionOut":
        return cls(id=p.id, name=p.name, version=p.version, prompt_content=p.prompt_content)


class BenchmarkRunRequest(BaseModel):
    prompt_version_id: int | None = None  # None = current default prompt (eval-v1)


class BenchmarkRunOut(BaseModel):
    id: int
    dataset_name: str
    prompt_version_label: str
    evaluation_model: str
    total_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    category_detection_rate: float
    average_latency_ms: float
    total_estimated_cost: float
    details: list = []

    @classmethod
    def from_model(cls, r, include_details: bool = False) -> "BenchmarkRunOut":
        return cls(
            id=r.id, dataset_name=r.dataset_name, prompt_version_label=r.prompt_version_label,
            evaluation_model=r.evaluation_model, total_cases=r.total_cases,
            true_positives=r.true_positives, false_positives=r.false_positives,
            true_negatives=r.true_negatives, false_negatives=r.false_negatives,
            precision=r.precision, recall=r.recall, f1_score=r.f1_score, accuracy=r.accuracy,
            category_detection_rate=r.category_detection_rate,
            average_latency_ms=r.average_latency_ms, total_estimated_cost=r.total_estimated_cost,
            details=(json.loads(r.details) if include_details else []),
        )
