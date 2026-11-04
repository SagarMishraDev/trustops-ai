"""Ingestion service: validation, normalization and storage.

Route files stay thin - all rules live here so CSV, JSON, REST and
webhooks behave identically:
  - timestamps must parse, messages must be non-empty
  - one bad record NEVER crashes the whole import; it is counted + reported
  - duplicates (same business + external conversation_id) are skipped,
    never stored twice
"""
import csv
import io
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.conversation import Conversation

REQUIRED_COLUMNS = ["conversation_id", "user_message", "assistant_response", "timestamp"]


def parse_timestamp(value) -> datetime:
    """Accept ISO timestamps like 2026-11-04T10:30:00 or with Z/offset."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)  # raises ValueError on bad input - caller handles it
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_record(raw: dict, source: str) -> dict:
    """Validate one raw record. Raises ValueError with a readable reason."""
    missing = [f for f in REQUIRED_COLUMNS if not str(raw.get(f) or "").strip()]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")
    return {
        "external_conversation_id": str(raw["conversation_id"]).strip(),
        "session_id": (str(raw["session_id"]).strip() if raw.get("session_id") else None),
        "user_message": str(raw["user_message"]).strip(),
        "assistant_response": str(raw["assistant_response"]).strip(),
        "timestamp": parse_timestamp(raw["timestamp"]),
        "source": source,
    }


def store_conversation(db: Session, business_id: int, normalized: dict) -> str:
    """Store one normalized record. Returns 'stored' or 'duplicate'."""
    exists = (
        db.query(Conversation)
        .filter(
            Conversation.business_id == business_id,
            Conversation.external_conversation_id == normalized["external_conversation_id"],
        )
        .first()
    )
    if exists:
        return "duplicate"
    db.add(Conversation(business_id=business_id, **normalized))
    try:
        db.commit()
    except IntegrityError:  # race-safe: unique constraint is the final guard
        db.rollback()
        return "duplicate"
    return "stored"


def import_records(db: Session, business_id: int, records: list[dict], source: str) -> dict:
    result = {"imported": 0, "duplicates_skipped": 0, "failed": 0, "errors": []}
    for i, raw in enumerate(records, start=1):
        try:
            normalized = normalize_record(raw, source)
        except ValueError as exc:
            result["failed"] += 1
            result["errors"].append(f"Record {i}: {exc}")
            continue
        outcome = store_conversation(db, business_id, normalized)
        if outcome == "stored":
            result["imported"] += 1
        else:
            result["duplicates_skipped"] += 1
    return result


def parse_csv(content: bytes) -> tuple[list[dict] | None, str | None]:
    """Returns (records, error). Error is set when the FILE itself is invalid."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "File is not valid UTF-8 text"
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return None, "CSV file is empty or has no header row"
    headers = [h.strip() for h in reader.fieldnames]
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing_cols:
        return None, f"Missing required column(s): {', '.join(missing_cols)}. Required: {', '.join(REQUIRED_COLUMNS)} (+ optional session_id)"
    records = [{(k.strip() if k else k): v for k, v in row.items() if k is not None} for row in reader]
    return records, None
