"""Evidence records: company-provided facts that evaluations verify
claims against. CRUD, scoped to the caller's business."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_business
from app.models.business import Business
from app.models.policy import EvidenceRecord
from app.schemas.policy import EvidenceCreate, EvidenceOut

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.post("", response_model=EvidenceOut, status_code=201)
def create_evidence(payload: EvidenceCreate, db: Session = Depends(get_db),
                    business: Business = Depends(get_current_business)):
    record = EvidenceRecord(business_id=business.id, topic=payload.topic.strip(),
                            content=payload.content.strip(), source=payload.source)
    db.add(record)
    db.commit()
    db.refresh(record)
    return EvidenceOut.from_model(record)


@router.get("", response_model=list[EvidenceOut])
def list_evidence(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    rows = db.query(EvidenceRecord).filter(EvidenceRecord.business_id == business.id).order_by(EvidenceRecord.id).all()
    return [EvidenceOut.from_model(e) for e in rows]


@router.delete("/{evidence_id}")
def delete_evidence(evidence_id: int, db: Session = Depends(get_db),
                    business: Business = Depends(get_current_business)):
    record = db.query(EvidenceRecord).filter(
        EvidenceRecord.id == evidence_id, EvidenceRecord.business_id == business.id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    db.delete(record)
    db.commit()
    return {"deleted": True, "evidence_id": evidence_id}
