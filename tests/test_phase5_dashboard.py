"""Phase 5 tests: analytics, reviews/queue, settings safety, dashboard serving, demo seed."""
from tests.conftest import make_business


def add_and_evaluate(client, headers, cid, user, assistant):
    r = client.post("/api/v1/conversations", headers=headers, json={
        "conversation_id": cid, "user_message": user, "assistant_response": assistant,
        "timestamp": "2026-11-04T10:30:00", "session_id": "S1"})
    convo_id = r.json()["id"]
    ev = client.post("/api/v1/evaluations", headers=headers, json={"conversation_id": convo_id})
    assert ev.status_code == 201, ev.text
    return convo_id, ev.json()


GOOD = ("What are your opening hours?", "We are open 9 AM to 9 PM, Monday to Saturday.")
REFUND = ("Can I get a refund?", "Your refund is approved.")


def test_overview_numbers_are_real(client):
    headers = make_business(client)
    add_and_evaluate(client, headers, "G001", *GOOD)
    add_and_evaluate(client, headers, "R001", *REFUND)
    o = client.get("/api/v1/analytics/overview", headers=headers).json()
    assert o["total_conversations"] == 2 and o["total_evaluations"] == 2
    assert o["passed"] == 1 and o["flagged"] == 1
    assert o["average_score"] == 82.5  # (100 + 65) / 2 - refund claim without a policy = one high issue; with a policy it would be 30 (see Phase 4 tests)
    assert o["high_risk"] == 1 and o["pending_reviews"] == 1
    assert o["total_estimated_cost"] == 0.0  # mock evaluator costs nothing - honest zero


def test_overview_isolation_zeroes(client):
    ha = make_business(client, "Biz A")
    hb = make_business(client, "Biz B")
    add_and_evaluate(client, ha, "G001", *GOOD)
    o = client.get("/api/v1/analytics/overview", headers=hb).json()
    assert o["total_conversations"] == 0 and o["total_evaluations"] == 0 and o["average_score"] is None


def test_issues_distribution_and_trends(client):
    headers = make_business(client)
    add_and_evaluate(client, headers, "R001", *REFUND)
    issues = client.get("/api/v1/analytics/issues", headers=headers).json()
    cats = {c["category"]: c["count"] for c in issues["by_category"]}
    assert cats.get("hallucination") == 1
    trends = client.get("/api/v1/analytics/trends", headers=headers, params={"days": 14}).json()
    assert len(trends) == 14 and sum(t["evaluations"] for t in trends) == 1
    assert trends[-1]["average_score"] == 65.0  # hallucination-only score; policy violation would add another -35


def test_review_flow_and_evaluation_immutable(client):
    headers = make_business(client)
    _, ev = add_and_evaluate(client, headers, "R001", *REFUND)
    queue = client.get("/api/v1/reviews/queue", headers=headers).json()
    assert [q["id"] for q in queue] == [ev["id"]]
    r = client.post(f"/api/v1/reviews/{ev['id']}", headers=headers,
                    json={"decision": "confirmed", "reviewer_name": "Sagar", "notes": "Correctly flagged."})
    assert r.status_code == 201 and r.json()["decision"] == "confirmed"
    # queue empties, history exists, and the AI evaluation itself is untouched
    assert client.get("/api/v1/reviews/queue", headers=headers).json() == []
    history = client.get(f"/api/v1/reviews/{ev['id']}", headers=headers).json()
    assert len(history) == 1 and history[0]["reviewer_name"] == "Sagar"
    after = client.get(f"/api/v1/evaluations/{ev['id']}", headers=headers).json()
    assert after["overall_score"] == ev["overall_score"] and after["status"] == ev["status"]


def test_review_isolation(client):
    ha = make_business(client, "Biz A")
    hb = make_business(client, "Biz B")
    _, ev = add_and_evaluate(client, ha, "R001", *REFUND)
    assert client.post(f"/api/v1/reviews/{ev['id']}", headers=hb,
                       json={"decision": "confirmed", "reviewer_name": "X"}).status_code == 404
    assert client.get("/api/v1/reviews/queue", headers=hb).json() == []


def test_settings_never_leaks_key(client):
    headers = make_business(client)
    r = client.get("/api/v1/settings", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_provider"] == "mock" and body["prompt_version"] == "eval-v1"
    assert "tok_" not in r.text and body["llm_api_key_configured"] is False


def test_demo_seed_is_idempotent(client):
    headers = make_business(client)
    first = client.post("/api/v1/demo/seed", headers=headers).json()
    assert first["policies_created"] == 5 and first["imported"] == 8 and first["evaluated"] == 8
    second = client.post("/api/v1/demo/seed", headers=headers).json()
    assert second["imported"] == 0 and second["evaluated"] == 0
    o = client.get("/api/v1/analytics/overview", headers=headers).json()
    assert o["total_conversations"] == 8 and o["total_evaluations"] == 8
    assert o["passed"] == 1 and o["flagged"] == 7  # only the opening-hours reply is clean


def test_dashboard_page_and_assets_served(client):
    page = client.get("/dashboard")
    assert page.status_code == 200 and "TrustOps" in page.text
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
