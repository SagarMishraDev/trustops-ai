"""Webhook ingestion for live chatbot systems.

POST /api/v1/webhooks/conversations  (header: X-API-Key)

Idempotency: the same conversation_id sent twice (retries happen in real
systems) returns 200 with duplicate=true and stores nothing new.
HMAC signature verification is a Phase 7 hardening item for specific
providers; API-key auth is enforced here from day one.
The endpoint only STORES the conversation - evaluation is scheduled by
later phases, so a slow evaluation can never block the sender's webhook.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_business
from app.models.business import Business
from app.schemas.conversation import ConversationCreate
from app.services import ingestion

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/conversations")
def receive_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    normalized = ingestion.normalize_record(payload.model_dump(), source="webhook")
    outcome = ingestion.store_conversation(db, business.id, normalized)
    return {
        "received": True,
        "conversation_id": payload.conversation_id,
        "duplicate": outcome == "duplicate",
        "status": "stored" if outcome == "stored" else "already_exists",
    }
