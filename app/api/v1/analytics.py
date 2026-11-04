"""Analytics: every number is computed from the real database for the
caller's business only. No cached or invented metrics."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_business
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.evaluation import Evaluation, EvaluationIssue
from app.models.review import HumanReview

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _eval_query(db: Session, business: Business):
    return db.query(Evaluation).join(Conversation).filter(Conversation.business_id == business.id)


@router.get("/overview")
def overview(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    total_conversations = db.query(Conversation).filter(Conversation.business_id == business.id).count()
    evals = _eval_query(db, business).all()
    total = len(evals)
    by_status = Counter(e.status for e in evals)
    avg_score = round(sum(e.overall_score for e in evals) / total, 1) if total else None
    reviewed_ids = {r.evaluation_id for r in db.query(HumanReview.evaluation_id).all()}
    pending = sum(1 for e in evals if e.human_review_required and e.id not in reviewed_ids)
    return {
        "total_conversations": total_conversations,
        "total_evaluations": total,
        "passed": by_status.get("passed", 0),
        "flagged": by_status.get("flagged", 0),
        "needs_review": by_status.get("needs_review", 0),
        "high_risk": sum(1 for e in evals if e.risk_level in ("high", "critical")),
        "average_score": avg_score,
        "pending_reviews": pending,
        "total_issues": sum(len(e.issues) for e in evals),
        "average_latency_ms": round(sum(e.latency_ms for e in evals) / total) if total else 0,
        "total_estimated_cost": round(sum(e.estimated_cost for e in evals), 6),
    }


@router.get("/issues")
def issues(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    rows = (db.query(EvaluationIssue).join(Evaluation).join(Conversation)
            .filter(Conversation.business_id == business.id).all())
    by_category = Counter(i.category for i in rows)
    by_severity = Counter(i.severity for i in rows)
    return {
        "by_category": [{"category": k, "count": v} for k, v in by_category.most_common()],
        "by_severity": [{"severity": k, "count": v} for k, v in by_severity.most_common()],
    }


@router.get("/trends")
def trends(days: int = 14, db: Session = Depends(get_db),
           business: Business = Depends(get_current_business)):
    days = max(1, min(days, 90))
    evals = _eval_query(db, business).all()
    today = datetime.now(timezone.utc).date()
    buckets: dict[str, list[int]] = {}
    for ev in evals:
        created = ev.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        buckets.setdefault(created.date().isoformat(), []).append(ev.overall_score)
    out = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        scores = buckets.get(day, [])
        out.append({
            "date": day,
            "evaluations": len(scores),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        })
    return out
