"""Shared test setup.

IMPORTANT ORDER: DATABASE_URL is set to a throwaway test file BEFORE the
app is imported, so tests can never touch the real development database.
Tables are emptied before every test so tests stay independent.
"""
import os
import pathlib

_test_db = pathlib.Path(__file__).parent / "test_trustops.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.business import Business  # noqa: E402
from app.models.conversation import Conversation  # noqa: E402
from app.models.evaluation import Evaluation, EvaluationIssue  # noqa: E402
from app.models.policy import EvidenceRecord, Policy  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    # children first - evaluations reference conversations, so a leftover
    # evaluation from an earlier test could otherwise join onto a new
    # conversation that reuses the same id
    db.query(EvaluationIssue).delete()
    db.query(Policy).delete()
    db.query(EvidenceRecord).delete()
    db.query(Evaluation).delete()
    db.query(Conversation).delete()
    db.query(Business).delete()
    db.commit()
    db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def make_business(client: TestClient, name: str = "Acme Support") -> dict:
    """Create a business and return headers with its API key."""
    r = client.post("/api/v1/businesses", json={"name": name})
    assert r.status_code == 201, r.text
    return {"X-API-Key": r.json()["api_key"]}


GOOD_PAYLOAD = {
    "conversation_id": "C001",
    "user_message": "Where is my order?",
    "assistant_response": "Your order is delivered.",
    "timestamp": "2026-11-04T10:30:00",
    "session_id": "S001",
}
