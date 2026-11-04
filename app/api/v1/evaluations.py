"""Evaluation endpoints: single, bulk, list, detail. All API-key protected
and scoped to the caller's business - you can only evaluate and read
evaluations of YOUR OWN conversations."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_business
from app.evaluation.evaluators import EvaluatorConfigError
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.evaluation import Evaluation
from app.schemas.evaluation import BulkEvaluationRequest, EvaluationOut, EvaluationRequest
from app.services import evaluation as evaluation_service

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


def _own_conversation(db: Session, business: Business, conversation_id: int) -> Conversation:
    convo = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.business_id == business.id).first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


def _run(db, convo, policies, evidence):
    try:
        return evaluation_service.evaluate_conversation(db, convo, policies, evidence)
    except EvaluatorConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("", response_model=EvaluationOut, status_code=201)
def evaluate_one(payload: EvaluationRequest, db: Session = Depends(get_db),
                 business: Business = Depends(get_current_business)):
    convo = _own_conversation(db, business, payload.conversation_id)
    ev = _run(db, convo, payload.policies, payload.evidence)
    return EvaluationOut.from_model(ev)


@router.post("/bulk", response_model=list[EvaluationOut])
def evaluate_bulk(payload: BulkEvaluationRequest, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    q = db.query(Conversation).filter(Conversation.business_id == business.id)
    if payload.conversation_ids:
        q = q.filter(Conversation.id.in_(payload.conversation_ids))
    conversations = q.order_by(Conversation.id).limit(200).all()
    return [EvaluationOut.from_model(_run(db, c, payload.policies, None)) for c in conversations]


@router.get("", response_model=list[EvaluationOut])
def list_evaluations(status: str | None = None, risk_level: str | None = None,
                     skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
                     db: Session = Depends(get_db),
                     business: Business = Depends(get_current_business)):
    q = (db.query(Evaluation).join(Conversation)
         .filter(Conversation.business_id == business.id))
    if status:
        q = q.filter(Evaluation.status == status)
    if risk_level:
        q = q.filter(Evaluation.risk_level == risk_level)
    rows = q.order_by(Evaluation.created_at.desc()).offset(skip).limit(limit).all()
    return [EvaluationOut.from_model(ev) for ev in rows]


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: int, db: Session = Depends(get_db),
                   business: Business = Depends(get_current_business)):
    ev = (db.query(Evaluation).join(Conversation)
          .filter(Evaluation.id == evaluation_id, Conversation.business_id == business.id).first())
    if ev is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return EvaluationOut.from_model(ev)
