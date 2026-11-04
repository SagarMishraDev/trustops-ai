"""Conversation schemas.

Incoming conversation text is UNTRUSTED DATA. It is validated here as
plain text and later treated as data to evaluate - never as instructions
for the evaluator (prompt-injection safety, built in from Phase 2).
"""
from datetime import datetime
from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=100)
    user_message: str = Field(min_length=1)
    assistant_response: str = Field(min_length=1)
    timestamp: datetime
    session_id: str | None = Field(default=None, max_length=100)


class ConversationOut(BaseModel):
    id: int
    conversation_id: str
    session_id: str | None
    user_message: str
    assistant_response: str
    timestamp: datetime
    source: str

    @classmethod
    def from_model(cls, c) -> "ConversationOut":
        return cls(
            id=c.id, conversation_id=c.external_conversation_id, session_id=c.session_id,
            user_message=c.user_message, assistant_response=c.assistant_response,
            timestamp=c.timestamp, source=c.source,
        )


class ImportResult(BaseModel):
    imported: int
    duplicates_skipped: int
    failed: int
    errors: list[str]
