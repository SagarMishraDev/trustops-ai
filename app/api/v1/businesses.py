"""Business registration: creates the tenant and its API key (shown once)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import generate_api_key, hash_api_key
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessCreated

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])


@router.post("", response_model=BusinessCreated, status_code=201)
def create_business(payload: BusinessCreate, db: Session = Depends(get_db)):
    api_key = generate_api_key()
    business = Business(name=payload.name.strip(), api_key_hash=hash_api_key(api_key))
    db.add(business)
    db.commit()
    db.refresh(business)
    return BusinessCreated(id=business.id, name=business.name, api_key=api_key)
