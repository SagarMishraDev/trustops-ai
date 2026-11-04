"""Conversation endpoints: REST create, CSV upload, JSON upload, list, get.

Every endpoint requires X-API-Key and only ever touches the caller's own
business data (tenant isolation).
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_business
from app.models.business import Business
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationCreate, ConversationOut, ImportResult
from app.services import ingestion

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


async def _read_upload(file: UploadFile, allowed_ext: str) -> bytes:
    if not (file.filename or "").lower().endswith(allowed_ext):
        raise HTTPException(status_code=400, detail=f"Only {allowed_ext} files are accepted")
    content = await file.read()
    max_bytes = get_settings().max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {get_settings().max_upload_size_mb} MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return content


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    normalized = ingestion.normalize_record(payload.model_dump(), source="api")
    outcome = ingestion.store_conversation(db, business.id, normalized)
    if outcome == "duplicate":
        raise HTTPException(status_code=409, detail=f"Conversation {payload.conversation_id} already exists for this business")
    convo = db.query(Conversation).filter(
        Conversation.business_id == business.id,
        Conversation.external_conversation_id == payload.conversation_id,
    ).first()
    return ConversationOut.from_model(convo)


@router.post("/upload", response_model=ImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    content = await _read_upload(file, ".csv")
    records, error = ingestion.parse_csv(content)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return ingestion.import_records(db, business.id, records, source="csv")


@router.post("/upload-json", response_model=ImportResult)
async def upload_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    content = await _read_upload(file, ".json")
    try:
        data = json.loads(content.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="File is not valid JSON")
    records = data.get("conversations") if isinstance(data, dict) else data
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise HTTPException(status_code=400, detail="JSON must be a list of conversation objects, or an object with a 'conversations' list")
    return ingestion.import_records(db, business.id, records, source="json")


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    source: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    q = db.query(Conversation).filter(Conversation.business_id == business.id)
    if source:
        q = q.filter(Conversation.source == source)
    if search:
        like = f"%{search}%"
        q = q.filter((Conversation.user_message.ilike(like)) | (Conversation.assistant_response.ilike(like)))
    rows = q.order_by(Conversation.timestamp.desc()).offset(skip).limit(limit).all()
    return [ConversationOut.from_model(c) for c in rows]


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    convo = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.business_id == business.id
    ).first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationOut.from_model(convo)
