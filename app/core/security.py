"""API-key authentication + webhook signature verification (Phase 7).

WHAT: Businesses authenticate with an API key sent as the X-API-Key
      header. Webhooks additionally carry an HMAC-SHA256 signature.
WHY:  Ingestion endpoints cannot be open to the internet - anyone could
      flood or read another business's conversations. A signature proves
      the exact request bytes came from the secret holder, and signing
      the timestamp makes captured requests expire (replay protection).
HOW:  API keys are random (secrets module); only the SHA-256 hash is
      stored, so a database leak does not leak usable keys. The webhook
      secret is the HMAC key itself, so it must be stored usable - it is
      shown once at creation and never returned by any GET endpoint.
"""
import hashlib
import hmac
import secrets
import time
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.business import Business


def generate_api_key() -> str:
    return "tok_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_webhook_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def compute_webhook_signature(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over "<timestamp>.<raw body>" - the Stripe-style scheme."""
    signed = f"{timestamp}.".encode("utf-8") + body
    return "sha256=" + hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def verify_webhook_signature(secret: str, timestamp: str, signature: str,
                             body: bytes, tolerance_seconds: int) -> tuple[bool, str]:
    """Returns (ok, reason) where reason is ok | stale | invalid."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, "invalid"
    if abs(int(time.time()) - ts) > tolerance_seconds:
        return False, "stale"
    expected = compute_webhook_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature or ""):
        return False, "invalid"
    return True, "ok"


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
