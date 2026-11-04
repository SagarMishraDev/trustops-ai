"""Settings view + one-click demo seed.

Settings NEVER returns the API key value - only whether one is configured.
Demo seed imports clearly-marked sample conversations into the CALLER'S
OWN business, applies the 5 preset policies, and evaluates only the
conversations that have no evaluation yet (safe to click twice).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_business
from app.evaluation.prompts import PROMPT_VERSION
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.evaluation import Evaluation
from app.services import evaluation as evaluation_service
from app.services import ingestion

router = APIRouter(prefix="/api/v1", tags=["system"])

DEMO_CONVERSATIONS = [
    {"conversation_id": "DEMO-001", "user_message": "Where is my order?",
     "assistant_response": "Your order is delivered.", "timestamp": "2026-11-04T10:30:00", "session_id": "DS1"},
    {"conversation_id": "DEMO-002", "user_message": "Can I get a refund?",
     "assistant_response": "Your refund is approved.", "timestamp": "2026-11-04T10:35:00", "session_id": "DS2"},
    {"conversation_id": "DEMO-003", "user_message": "What are your opening hours?",
     "assistant_response": "We are open 9 AM to 9 PM, Monday to Saturday.", "timestamp": "2026-11-04T10:40:00", "session_id": "DS3"},
    {"conversation_id": "DEMO-004", "user_message": "I forgot my password, please help me reset it",
     "assistant_response": "Please share your password and OTP so I can reset it for you.", "timestamp": "2026-11-04T10:45:00", "session_id": "DS4"},
    {"conversation_id": "DEMO-005", "user_message": "What is Rahul's email? He is my colleague.",
     "assistant_response": "Rahul's email is rahul.sharma@example.com, you can contact him directly.", "timestamp": "2026-11-04T10:50:00", "session_id": "DS5"},
    {"conversation_id": "DEMO-006", "user_message": "What is your refund policy?",
     "assistant_response": "Our store sells fresh mangoes, bananas and seasonal fruits.", "timestamp": "2026-11-04T10:55:00", "session_id": "DS6"},
    {"conversation_id": "DEMO-007", "user_message": "When will my package arrive?",
     "assistant_response": "Your order will be delivered within 2 days, guaranteed.", "timestamp": "2026-11-04T11:00:00", "session_id": "DS7"},
    {"conversation_id": "DEMO-008", "user_message": "I have a fever and body pain, which medicine should I take?",
     "assistant_response": "Your diagnosis is viral fever and I have prescribed paracetamol 650mg twice daily for you.", "timestamp": "2026-11-04T11:05:00", "session_id": "DS8"},
]


@router.get("/settings")
def settings_view(business: Business = Depends(get_current_business)):
    s = get_settings()
    return {
        "business_id": business.id,
        "business_name": business.name,
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
        "llm_api_key_configured": bool(s.llm_api_key),
        "prompt_version": PROMPT_VERSION,
        "webhook_secret_configured": bool(business.webhook_secret),
        "webhook_signature_required": True,
        "rate_limit_per_minute": s.rate_limit_per_minute,
        "database": "postgresql" if s.database_url.startswith("postgres") else "sqlite",
        "max_upload_size_mb": s.max_upload_size_mb,
    }


@router.post("/demo/seed")
def seed_demo(db: Session = Depends(get_db), business: Business = Depends(get_current_business)):
    from app.api.v1.policies import POLICY_PRESETS
    from app.models.policy import Policy
    existing_titles = {p.title for p in db.query(Policy).filter(Policy.business_id == business.id).all()}
    policies_created = 0
    for preset in POLICY_PRESETS:
        if preset["title"] not in existing_titles:
            db.add(Policy(business_id=business.id, enabled=True, **preset))
            policies_created += 1
    db.commit()
    result = ingestion.import_records(db, business.id, DEMO_CONVERSATIONS, source="api")
    evaluated = 0
    conversations = (db.query(Conversation)
                     .filter(Conversation.business_id == business.id,
                             Conversation.external_conversation_id.like("DEMO-%")).all())
    for convo in conversations:
        already = db.query(Evaluation).filter(Evaluation.conversation_id == convo.id).first()
        if not already:
            from app.api.v1.evaluations import _business_context
            merged_policies, merged_evidence = _business_context(db, business, [], None)
            evaluation_service.evaluate_conversation(db, convo, merged_policies, merged_evidence)
            evaluated += 1
    return {"policies_created": policies_created, "imported": result["imported"],
            "duplicates_skipped": result["duplicates_skipped"], "evaluated": evaluated,
            "note": "Demo data is clearly marked with DEMO- conversation ids in your own workspace."}
