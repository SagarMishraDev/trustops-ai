"""Phase 2 tests: ingestion (REST, CSV, JSON, webhook), auth, isolation."""
import io
import json
from tests.conftest import GOOD_PAYLOAD, make_business, make_business_full, signed_webhook_post


def test_create_business_returns_api_key_once(client):
    r = client.post("/api/v1/businesses", json={"name": "Acme"})
    assert r.status_code == 201
    assert r.json()["api_key"].startswith("tok_")


def test_conversations_require_api_key(client):
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.get("/api/v1/conversations", headers={"X-API-Key": "tok_wrong"}).status_code == 401


def test_create_and_get_conversation(client):
    headers = make_business(client)
    r = client.post("/api/v1/conversations", json=GOOD_PAYLOAD, headers=headers)
    assert r.status_code == 201, r.text
    convo_id = r.json()["id"]
    got = client.get(f"/api/v1/conversations/{convo_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["conversation_id"] == "C001"
    assert got.json()["source"] == "api"


def test_duplicate_conversation_rejected_409(client):
    headers = make_business(client)
    assert client.post("/api/v1/conversations", json=GOOD_PAYLOAD, headers=headers).status_code == 201
    assert client.post("/api/v1/conversations", json=GOOD_PAYLOAD, headers=headers).status_code == 409


def test_business_data_isolation(client):
    headers_a = make_business(client, "Business A")
    headers_b = make_business(client, "Business B")
    r = client.post("/api/v1/conversations", json=GOOD_PAYLOAD, headers=headers_a)
    convo_id = r.json()["id"]
    # B sees an empty list and a 404 - never A's data, never a leak of existence
    assert client.get("/api/v1/conversations", headers=headers_b).json() == []
    assert client.get(f"/api/v1/conversations/{convo_id}", headers=headers_b).status_code == 404


CSV_GOOD = (
    "conversation_id,user_message,assistant_response,timestamp,session_id\n"
    'C001,"Where is my order?","Your order is delivered.",2026-11-04T10:30:00,S001\n'
    'C002,"Can I get a refund?","Your refund is approved.",2026-11-04T10:35:00,S002\n'
)


def _upload(client, headers, filename, data: bytes, url="/api/v1/conversations/upload"):
    return client.post(url, headers=headers, files={"file": (filename, io.BytesIO(data), "text/csv")})


def test_csv_upload_counts_and_duplicates(client):
    headers = make_business(client)
    r = _upload(client, headers, "c.csv", CSV_GOOD.encode())
    assert r.status_code == 200, r.text
    assert r.json() == {"imported": 2, "duplicates_skipped": 0, "failed": 0, "errors": []}
    # uploading the same file again stores nothing new
    r2 = _upload(client, headers, "c.csv", CSV_GOOD.encode())
    assert r2.json()["imported"] == 0 and r2.json()["duplicates_skipped"] == 2
    assert len(client.get("/api/v1/conversations", headers=headers).json()) == 2


def test_csv_missing_column_is_400_not_crash(client):
    headers = make_business(client)
    bad = b"conversation_id,user_message\nC001,Hello\n"
    assert _upload(client, headers, "bad.csv", bad).status_code == 400


def test_csv_bad_rows_counted_not_crashing(client):
    headers = make_business(client)
    mixed = (
        "conversation_id,user_message,assistant_response,timestamp,session_id\n"
        "G001,Hello,Hi there,2026-11-04T10:30:00,S001\n"
        "B001,Hello,Hi there,not-a-date,S002\n"
        "B002,,Hi there,2026-11-04T10:30:00,S003\n"
    )
    r = _upload(client, headers, "mixed.csv", mixed.encode())
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 1 and body["failed"] == 2 and len(body["errors"]) == 2


def test_wrong_file_type_rejected(client):
    headers = make_business(client)
    assert _upload(client, headers, "data.txt", b"hello").status_code == 400


def test_json_upload_list_and_wrapped(client):
    headers = make_business(client)
    rows = [dict(GOOD_PAYLOAD, conversation_id="J001")]
    r = _upload(client, headers, "c.json", json.dumps(rows).encode(), url="/api/v1/conversations/upload-json")
    assert r.json()["imported"] == 1
    wrapped = {"conversations": [dict(GOOD_PAYLOAD, conversation_id="J002")]}
    r2 = _upload(client, headers, "c2.json", json.dumps(wrapped).encode(), url="/api/v1/conversations/upload-json")
    assert r2.json()["imported"] == 1
    assert len(client.get("/api/v1/conversations", headers=headers).json()) == 2


def test_json_invalid_file_is_400(client):
    headers = make_business(client)
    r = _upload(client, headers, "c.json", b"{not json", url="/api/v1/conversations/upload-json")
    assert r.status_code == 400


def test_webhook_idempotent(client):
    headers, api_key, secret = make_business_full(client)
    payload = dict(GOOD_PAYLOAD, conversation_id="W001")
    r1 = signed_webhook_post(client, api_key, secret, payload)
    assert r1.status_code == 200 and r1.json()["duplicate"] is False
    r2 = signed_webhook_post(client, api_key, secret, payload)
    assert r2.status_code == 200 and r2.json()["duplicate"] is True
    rows = client.get("/api/v1/conversations", headers=headers).json()
    assert len(rows) == 1 and rows[0]["source"] == "webhook"


def test_webhook_requires_auth(client):
    assert client.post("/api/v1/webhooks/conversations", json=GOOD_PAYLOAD).status_code == 401
