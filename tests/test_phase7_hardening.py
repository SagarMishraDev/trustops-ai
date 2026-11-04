"""Phase 7 tests: signed webhooks, replay protection, structured errors,
request IDs, security headers and rate limiting."""
import time
from fastapi.testclient import TestClient
from tests.conftest import GOOD_PAYLOAD, make_business, make_business_full, signed_webhook_post


def test_business_creation_returns_webhook_secret_once(client):
    r = client.post("/api/v1/businesses", json={"name": "Secret Biz"})
    body = r.json()
    assert body["webhook_secret"].startswith("whsec_")
    # settings proves it is configured WITHOUT ever returning the value
    s = client.get("/api/v1/settings", headers={"X-API-Key": body["api_key"]})
    assert s.json()["webhook_secret_configured"] is True
    assert s.json()["webhook_signature_required"] is True
    assert "whsec_" not in s.text


def test_signed_webhook_accepted_and_idempotent(client):
    _, key, secret = make_business_full(client)
    r1 = signed_webhook_post(client, key, secret, GOOD_PAYLOAD)
    assert r1.status_code == 200 and r1.json()["duplicate"] is False
    r2 = signed_webhook_post(client, key, secret, GOOD_PAYLOAD)
    assert r2.status_code == 200 and r2.json()["duplicate"] is True


def test_unsigned_webhook_rejected(client):
    headers = make_business(client)
    r = client.post("/api/v1/webhooks/conversations", headers=headers, json=GOOD_PAYLOAD)
    assert r.status_code == 401 and r.json()["error_code"] == "missing_signature"


def test_tampered_body_rejected(client):
    _, key, secret = make_business_full(client)
    import json as _json
    from app.core.security import compute_webhook_signature
    good_body = _json.dumps(GOOD_PAYLOAD).encode()
    ts = str(int(time.time()))
    sig = compute_webhook_signature(secret, ts, good_body)
    tampered = _json.dumps({**GOOD_PAYLOAD, "assistant_response": "Forged response."}).encode()
    r = client.post("/api/v1/webhooks/conversations", content=tampered, headers={
        "X-API-Key": key, "X-TrustOps-Timestamp": ts, "X-TrustOps-Signature": sig,
        "Content-Type": "application/json"})
    assert r.status_code == 401 and r.json()["error_code"] == "invalid_signature"


def test_wrong_secret_rejected(client):
    _, key, secret = make_business_full(client)
    r = signed_webhook_post(client, key, secret, GOOD_PAYLOAD, sign_with="whsec_attacker_controlled")
    assert r.status_code == 401 and r.json()["error_code"] == "invalid_signature"


def test_stale_timestamp_rejected_replay_protection(client):
    _, key, secret = make_business_full(client)
    old_ts = int(time.time()) - 3600  # one hour old, tolerance is 5 minutes
    r = signed_webhook_post(client, key, secret, GOOD_PAYLOAD, timestamp=old_ts)
    assert r.status_code == 401 and r.json()["error_code"] == "stale_timestamp"


def test_structured_errors_and_request_id(client):
    headers = make_business(client)
    r = client.get("/api/v1/conversations/99999", headers=headers)
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "not_found" and body["request_id"]
    assert r.headers["X-Request-ID"] == body["request_id"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    h = client.get("/health")
    assert h.headers.get("X-Request-ID")


def test_rate_limit_returns_429_with_retry_after():
    from app.main import create_app
    tapp = create_app()
    tapp.state.rate_limit_per_minute = 5
    tc = TestClient(tapp)
    r = tc.post("/api/v1/businesses", json={"name": "Rate Biz"})  # registration is exempt
    assert r.status_code == 201
    headers = {"X-API-Key": r.json()["api_key"]}
    statuses = [tc.get("/api/v1/settings", headers=headers).status_code for _ in range(9)]
    assert statuses[:5] == [200] * 5
    assert 429 in statuses[5:]
    limited = tc.get("/api/v1/settings", headers=headers)
    assert limited.status_code == 429
    assert limited.json()["error_code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1


def test_signed_but_bad_shape_is_422(client):
    _, key, secret = make_business_full(client)
    r = signed_webhook_post(client, key, secret, {"foo": "bar"})
    assert r.status_code == 422 and r.json()["error_code"] == "validation_error"
