"""Webhook ingestion for live chatbot systems - SIGNED (Phase 7).

POST /api/v1/webhooks/conversations
Headers: X-API-Key, X-TrustOps-Timestamp (unix seconds),
         X-TrustOps-Signature: sha256=<HMAC-SHA256(secret, "<ts>.<body>")>

WHY SIGNING: an API key identifies the caller, but a signature proves
the exact bytes were produced by the secret holder and are fresh -
captured requests die after the 5-minute tolerance window (replay
protection), and tampered bodies fail verification.
Idempotency: the same conversation_id sent twice returns 200 with
duplicate=true and stores nothing new.
"""
import json
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_business, verify_webhook_signature
from app.models.business import Business
from app.schemas.conversation import ConversationCreate
from app.services import ingestion

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _err(request: Request, status_code: int, detail: str, code: str, **extra):
    return JSONResponse(status_code=status_code, content={
        "detail": detail, "error_code": code,
        "request_id": getattr(request.state, "request_id", None), **extra})


@router.post("/conversations")
async def receive_conversation(
    request: Request,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    body = await request.body()
    timestamp = request.headers.get("x-trustops-timestamp")
    signature = request.headers.get("x-trustops-signature")
    if not timestamp or not signature:
        return _err(request, 401,
                    "Missing X-TrustOps-Timestamp or X-TrustOps-Signature header",
                    "missing_signature")
    ok, reason = verify_webhook_signature(
        business.webhook_secret, timestamp, signature, body,
        get_settings().webhook_timestamp_tolerance_seconds)
    if not ok:
        if reason == "stale":
            return _err(request, 401,
                        "Webhook timestamp is outside the allowed 5-minute window (replay protection)",
                        "stale_timestamp")
        return _err(request, 401, "Webhook signature verification failed", "invalid_signature")
    try:
        data = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return _err(request, 422, "Request body is not valid JSON", "invalid_json")
    try:
        payload = ConversationCreate(**data)
    except ValidationError as exc:
        return _err(request, 422, "Invalid conversation payload", "validation_error",
                    errors=jsonable_encoder(exc.errors()))
    normalized = ingestion.normalize_record(payload.model_dump(), source="webhook")
    outcome = ingestion.store_conversation(db, business.id, normalized)
    return {
        "received": True,
        "conversation_id": payload.conversation_id,
        "duplicate": outcome == "duplicate",
        "status": "stored" if outcome == "stored" else "already_exists",
    }
