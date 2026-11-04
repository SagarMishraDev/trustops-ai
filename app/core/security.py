"""API-key authentication.

WHAT: Businesses authenticate with an API key sent as the X-API-Key header.
WHY:  Ingestion endpoints cannot be open to the internet - anyone could
      flood or read another business's conversations.
HOW:  Keys are random (secrets module). Only the SHA-256 hash is stored,
      so a database leak does not leak usable keys. Lookup is by hash,
      and every query after auth is scoped to that one business.
"""
import hashlib
import secrets
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.business import Business


def generate_api_key() -> str:
    return "tok_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_current_business(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Business:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    business = db.query(Business).filter(Business.api_key_hash == hash_api_key(x_api_key)).first()
    if business is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return business
