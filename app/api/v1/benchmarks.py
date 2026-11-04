"""Benchmark + prompt-version endpoints.

HONEST COMPARISON RULE: prompt content only changes behaviour when a real
LLM evaluator is configured. With the mock evaluator, runs under
different prompt labels produce identical metrics - the compare response
says so explicitly instead of inventing a winner.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_business
from app.evaluation.evaluators import EvaluatorConfigError
from app.models.benchmark import BenchmarkRun, PromptVersion
from app.models.business import Business
from app.schemas.benchmark import (BenchmarkRunOut, BenchmarkRunRequest,
                                    PromptVersionCreate, PromptVersionOut)
from app.services import benchmark as benchmark_service

router = APIRouter(prefix="/api/v1", tags=["benchmarks"])


# ---- prompt versions ----
@router.post("/prompt-versions", response_model=PromptVersionOut, status_code=201)
def create_prompt_version(payload: PromptVersionCreate, db: Session = Depends(get_db),
                          business: Business = Depends(get_current_business)):
    pv = PromptVersion(business_id=business.id, name=payload.name.strip(),
                       version=payload.version.strip(), prompt_content=payload.prompt_content)
    db.add(pv)
    db.commit()
    db.refresh(pv)
    return PromptVersionOut.from_model(pv)


@router.get("/prompt-versions", response_model=list[PromptVersionOut])
def list_prompt_versions(db: Session = Depends(get_db),
                         business: Business = Depends(get_current_business)):
    rows = db.query(PromptVersion).filter(PromptVersion.business_id == business.id).order_by(PromptVersion.id).all()
    return [PromptVersionOut.from_model(p) for p in rows]


# ---- benchmark runs ----
@router.post("/benchmarks/run", response_model=BenchmarkRunOut, status_code=201)
def run_benchmark(payload: BenchmarkRunRequest, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    label, content = None, None
    if payload.prompt_version_id is not None:
        pv = db.query(PromptVersion).filter(
            PromptVersion.id == payload.prompt_version_id,
            PromptVersion.business_id == business.id).first()
        if pv is None:
            raise HTTPException(status_code=404, detail="Prompt version not found")
        label, content = f"{pv.name}@{pv.version}", pv.prompt_content
    try:
        run = benchmark_service.run_benchmark(db, business, label, content)
    except EvaluatorConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return BenchmarkRunOut.from_model(run, include_details=True)


@router.get("/benchmarks", response_model=list[BenchmarkRunOut])
def list_runs(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    rows = (db.query(BenchmarkRun).filter(BenchmarkRun.business_id == business.id)
            .order_by(BenchmarkRun.created_at.desc()).all())
    return [BenchmarkRunOut.from_model(r) for r in rows]


@router.get("/benchmarks/{run_id}", response_model=BenchmarkRunOut)
def get_run(run_id: int, db: Session = Depends(get_db),
            business: Business = Depends(get_current_business)):
    run = db.query(BenchmarkRun).filter(
        BenchmarkRun.id == run_id, BenchmarkRun.business_id == business.id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return BenchmarkRunOut.from_model(run, include_details=True)


@router.get("/benchmarks/compare/{a_id}/{b_id}")
def compare_runs(a_id: int, b_id: int, db: Session = Depends(get_db),
                 business: Business = Depends(get_current_business)):
    def _get(rid):
        run = db.query(BenchmarkRun).filter(
            BenchmarkRun.id == rid, BenchmarkRun.business_id == business.id).first()
        if run is None:
            raise HTTPException(status_code=404, detail=f"Benchmark run {rid} not found")
        return run
    a, b = _get(a_id), _get(b_id)
    keys = ["precision", "recall", "f1_score", "accuracy", "category_detection_rate"]
    diff = {k: round(getattr(b, k) - getattr(a, k), 4) for k in keys}
    if get_settings().llm_provider.lower() == "mock":
        note = ("Both runs used the mock evaluator: prompt text does not change mock "
                "behaviour, so identical metrics are expected. Configure a real LLM "
                "provider to compare prompts meaningfully.")
        winner = "tie (mock evaluator - prompt has no effect)"
    elif diff["f1_score"] > 0:
        winner = b.prompt_version_label
        note = "Winner decided by F1 score on the same labeled dataset."
    elif diff["f1_score"] < 0:
        winner = a.prompt_version_label
        note = "Winner decided by F1 score on the same labeled dataset."
    else:
        winner = "tie"
        note = "Identical F1 on this dataset - compare precision/recall trade-offs."
    return {"a": BenchmarkRunOut.from_model(a).model_dump(),
            "b": BenchmarkRunOut.from_model(b).model_dump(),
            "difference_b_minus_a": diff, "winner_by_f1": winner, "note": note}
