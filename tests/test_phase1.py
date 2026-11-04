"""Phase 1 tests: root and health endpoints must work."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_returns_app_info():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "TrustOps AI"
    assert body["status"] == "running"


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unknown_route_is_404():
    assert client.get("/does-not-exist").status_code == 404
