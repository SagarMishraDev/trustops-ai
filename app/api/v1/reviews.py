"""Human review queue + decisions.

Queue = evaluations that require human review and have NO review yet.
Submitting a review never modifies the evaluation - it appends a
HumanReview record.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_business
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.evaluation import Evaluation
from app.models.review import HumanReview
from app.schemas.evaluation import EvaluationOut
from app.schemas.review import ReviewCreate, ReviewOut

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


def _own_evaluation(db: Session, business: Business, evaluation_id: int) -> Evaluation:
    ev = (db.query(Evaluation).join(Conversation)
          .filter(Evaluation.id == evaluation_id, Conversation.business_id == business.id).first())
    if ev is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return ev


@router.get("/queue", response_model=list[EvaluationOut])
def review_queue(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    reviewed_ids = {r.evaluation_id for r in db.query(HumanReview.evaluation_id).all()}
    q = (db.query(Evaluation).join(Conversation)
         .filter(Conversation.business_id == business.id,
                 Evaluation.human_review_required.is_(True))
         .order_by(Evaluation.created_at.desc()))
    return [EvaluationOut.from_model(ev) for ev in q.all() if ev.id not in reviewed_ids]


@router.get("", response_model=list[ReviewOut])
def list_reviews(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    rows = (db.query(HumanReview).join(Evaluation).join(Conversation)
            .filter(Conversation.business_id == business.id)
            .order_by(HumanReview.reviewed_at.desc()).limit(200).all())
    return [ReviewOut.from_model(r) for r in rows]


@router.get("/{evaluation_id}", response_model=list[ReviewOut])
def reviews_for_evaluation(evaluation_id: int, db: Session = Depends(get_db),
                           business: Business = Depends(get_current_business)):
    _own_evaluation(db, business, evaluation_id)
    rows = (db.query(HumanReview).filter(HumanReview.evaluation_id == evaluation_id)
            .order_by(HumanReview.reviewed_at.desc()).all())
    return [ReviewOut.from_model(r) for r in rows]


@router.post("/{evaluation_id}", response_model=ReviewOut, status_code=201)
def submit_review(evaluation_id: int, payload: ReviewCreate, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    _own_evaluation(db, business, evaluation_id)
    review = HumanReview(evaluation_id=evaluation_id, reviewer_name=payload.reviewer_name.strip(),
                         decision=payload.decision, notes=payload.notes)
    db.add(review)
    db.commit()
    db.refresh(review)
    return ReviewOut.from_model(review)
