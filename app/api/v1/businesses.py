"""Business registration: creates the tenant, its API key and its webhook
signing secret (both shown exactly once, in this response)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import generate_api_key, generate_webhook_secret, hash_api_key
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessCreated

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])


@router.post("", response_model=BusinessCreated, status_code=201)
def create_business(payload: BusinessCreate, db: Session = Depends(get_db)):
    api_key = generate_api_key()
    webhook_secret = generate_webhook_secret()
    business = Business(name=payload.name.strip(), api_key_hash=hash_api_key(api_key),
                        webhook_secret=webhook_secret)
    db.add(business)
    db.commit()
    db.refresh(business)
    return BusinessCreated(id=business.id, name=business.name, api_key=api_key,
                           webhook_secret=webhook_secret)
