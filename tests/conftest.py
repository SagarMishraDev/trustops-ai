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
from app.models.review import HumanReview  # noqa: E402
from app.models.benchmark import BenchmarkRun, PromptVersion  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    # children first - evaluations reference conversations, so a leftover
    # evaluation from an earlier test could otherwise join onto a new
    # conversation that reuses the same id
    db.query(HumanReview).delete()
    db.query(BenchmarkRun).delete()
    db.query(PromptVersion).delete()
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


def make_business_full(client: TestClient, name: str = "Acme Support"):
    """Create a business; return (headers, api_key, webhook_secret)."""
    r = client.post("/api/v1/businesses", json={"name": name})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"X-API-Key": body["api_key"]}, body["api_key"], body["webhook_secret"]


def signed_webhook_post(client: TestClient, api_key: str, secret: str, payload,
                        timestamp: int | None = None, sign_with: str | None = None):
    """POST a webhook exactly like a real signed sender (Phase 7 scheme)."""
    import json as _json
    import time as _time
    from app.core.security import compute_webhook_signature
    body = payload if isinstance(payload, bytes) else _json.dumps(payload).encode("utf-8")
    ts = str(timestamp if timestamp is not None else int(_time.time()))
    signature = compute_webhook_signature(sign_with or secret, ts, body)
    return client.post("/api/v1/webhooks/conversations", content=body, headers={
        "X-API-Key": api_key, "X-TrustOps-Timestamp": ts,
        "X-TrustOps-Signature": signature, "Content-Type": "application/json"})


GOOD_PAYLOAD = {
    "conversation_id": "C001",
    "user_message": "Where is my order?",
    "assistant_response": "Your order is delivered.",
    "timestamp": "2026-11-04T10:30:00",
    "session_id": "S001",
}
