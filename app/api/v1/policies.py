"""Policy management: CRUD + presets. Everything is scoped to the
caller's business - another business's policy id returns 404, never data."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_business
from app.models.business import Business
from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyOut, PolicyUpdate

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])

POLICY_PRESETS = [
    {"title": "Refund approval reserved",
     "description": "Refunds are money decisions - the bot can take a request, never approve it.",
     "rule_text": "Only authorized staff can approve refunds. The chatbot must not approve or process refunds."},
    {"title": "No unconfirmed delivery promises",
     "description": "Delivery dates must come from the actual order system.",
     "rule_text": "The chatbot must not promise unconfirmed delivery dates or guaranteed delivery timelines."},
    {"title": "Never request credentials",
     "description": "Passwords and OTPs are never asked for, in any situation.",
     "rule_text": "Customer passwords, OTPs, PINs and CVVs must never be requested by the chatbot."},
    {"title": "No other customer's data",
     "description": "One customer's information is never shared with another.",
     "rule_text": "The chatbot must not disclose another customer's personal data, email, phone number or address."},
    {"title": "Escalate medical and financial decisions",
     "description": "Health and money decisions need a qualified human.",
     "rule_text": "Medical or financial decisions must be escalated to a qualified human. The chatbot must not give a diagnosis, prescription, loan or investment decision."},
]


def _own_policy(db: Session, business: Business, policy_id: int) -> Policy:
    policy = db.query(Policy).filter(Policy.id == policy_id, Policy.business_id == business.id).first()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.get("/presets")
def list_presets():
    return POLICY_PRESETS


@router.post("/presets/apply")
def apply_presets(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    created, skipped = 0, 0
    existing = {p.title for p in db.query(Policy).filter(Policy.business_id == business.id).all()}
    for preset in POLICY_PRESETS:
        if preset["title"] in existing:
            skipped += 1
            continue
        db.add(Policy(business_id=business.id, enabled=True, **preset))
        created += 1
    db.commit()
    return {"created": created, "skipped_existing": skipped}


@router.post("", response_model=PolicyOut, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    policy = Policy(business_id=business.id, title=payload.title.strip(),
                    description=payload.description, rule_text=payload.rule_text.strip(),
                    enabled=payload.enabled)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyOut.from_model(policy)


@router.get("", response_model=list[PolicyOut])
def list_policies(enabled_only: bool = False, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    q = db.query(Policy).filter(Policy.business_id == business.id)
    if enabled_only:
        q = q.filter(Policy.enabled.is_(True))
    return [PolicyOut.from_model(p) for p in q.order_by(Policy.id).all()]


@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: int, db: Session = Depends(get_db),
               business: Business = Depends(get_current_business)):
    return PolicyOut.from_model(_own_policy(db, business, policy_id))


@router.put("/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: int, payload: PolicyUpdate, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    policy = _own_policy(db, business, policy_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return PolicyOut.from_model(policy)


@router.delete("/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db),
                  business: Business = Depends(get_current_business)):
    policy = _own_policy(db, business, policy_id)
    db.delete(policy)
    db.commit()
    return {"deleted": True, "policy_id": policy_id}
