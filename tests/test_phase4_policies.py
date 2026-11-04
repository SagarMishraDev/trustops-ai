"""Phase 4 tests: policy CRUD/presets, generalized rules, evidence, auto-apply."""
from tests.conftest import make_business
from app.evaluation.deterministic import check_policies


def add_conversation(client, headers, cid, user, assistant):
    r = client.post("/api/v1/conversations", headers=headers, json={
        "conversation_id": cid, "user_message": user, "assistant_response": assistant,
        "timestamp": "2026-11-04T10:30:00", "session_id": "S1"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def evaluate(client, headers, convo_id, **extra):
    r = client.post("/api/v1/evaluations", headers=headers, json={"conversation_id": convo_id, **extra})
    assert r.status_code == 201, r.text
    return r.json()


REFUND = ("Can I get a refund?", "Your refund is approved.")
REFUND_POLICY = {"title": "Refund approval reserved",
                 "rule_text": "Only authorized staff can approve refunds."}


# ---------- policy engine units ----------
def test_engine_generalizes_beyond_refunds():
    cases = [
        ("Your order will be delivered within 2 days.", "The chatbot must not promise unconfirmed delivery dates."),
        ("I can give you a 50 percent discount.", "Chatbot must never offer discounts without manager approval."),
        ("Your diagnosis is diabetes and I have prescribed metformin.", "Medical decisions must be escalated to a human."),
    ]
    for response, rule in cases:
        issues = check_policies(response, [rule])
        assert any(i.category == "policy_violation" for i in issues), (response, rule)


def test_engine_ignores_informational_policies_and_clean_replies():
    assert check_policies("Your refund is approved.", ["Our refund window is 30 days."]) == []
    assert check_policies("We are open 9 AM to 9 PM.", ["Only authorized staff can approve refunds."]) == []


# ---------- CRUD ----------
def test_policy_crud_lifecycle(client):
    headers = make_business(client)
    r = client.post("/api/v1/policies", headers=headers, json=REFUND_POLICY)
    assert r.status_code == 201 and r.json()["enabled"] is True
    pid = r.json()["id"]
    assert len(client.get("/api/v1/policies", headers=headers).json()) == 1
    upd = client.put(f"/api/v1/policies/{pid}", headers=headers, json={"enabled": False})
    assert upd.json()["enabled"] is False
    assert client.delete(f"/api/v1/policies/{pid}", headers=headers).json()["deleted"] is True
    assert client.get("/api/v1/policies", headers=headers).json() == []


def test_policy_isolation(client):
    ha = make_business(client, "Biz A")
    hb = make_business(client, "Biz B")
    pid = client.post("/api/v1/policies", headers=ha, json=REFUND_POLICY).json()["id"]
    assert client.get("/api/v1/policies", headers=hb).json() == []
    assert client.get(f"/api/v1/policies/{pid}", headers=hb).status_code == 404
    assert client.put(f"/api/v1/policies/{pid}", headers=hb, json={"enabled": False}).status_code == 404
    assert client.delete(f"/api/v1/policies/{pid}", headers=hb).status_code == 404


def test_presets_apply_once(client):
    headers = make_business(client)
    r = client.post("/api/v1/policies/presets/apply", headers=headers)
    assert r.json() == {"created": 5, "skipped_existing": 0}
    r2 = client.post("/api/v1/policies/presets/apply", headers=headers)
    assert r2.json() == {"created": 0, "skipped_existing": 5}
    assert len(client.get("/api/v1/policies", headers=headers).json()) == 5


# ---------- auto-apply in evaluations ----------
def test_enabled_db_policy_auto_applies_and_records_policy(client):
    headers = make_business(client)
    pid = client.post("/api/v1/policies", headers=headers, json=REFUND_POLICY).json()["id"]
    cid = add_conversation(client, headers, "R001", *REFUND)
    body = evaluate(client, headers, cid)  # NOTE: no policies passed in the request
    pv = [i for i in body["issues"] if i["category"] == "policy_violation"]
    assert pv, body
    assert pv[0]["policy_id"] == pid and pv[0]["policy_title"] == "Refund approval reserved"
    assert pv[0]["evidence"] == REFUND_POLICY["rule_text"]


def test_disabled_policy_does_not_apply(client):
    headers = make_business(client)
    client.post("/api/v1/policies", headers=headers, json={**REFUND_POLICY, "enabled": False})
    cid = add_conversation(client, headers, "R001", *REFUND)
    body = evaluate(client, headers, cid)
    assert not any(i["category"] == "policy_violation" for i in body["issues"])


def test_delivery_policy_auto_applies(client):
    headers = make_business(client)
    client.post("/api/v1/policies", headers=headers, json={
        "title": "No delivery promises", "rule_text": "The chatbot must not promise unconfirmed delivery dates."})
    cid = add_conversation(client, headers, "D001", "When will my order arrive?",
                           "Your order will be delivered within 2 days, guaranteed.")
    body = evaluate(client, headers, cid)
    assert any(i["category"] == "policy_violation" and i["policy_title"] == "No delivery promises"
               for i in body["issues"])


# ---------- evidence ----------
def test_evidence_record_auto_verifies_claim(client):
    headers = make_business(client)
    r = client.post("/api/v1/evidence", headers=headers, json={
        "topic": "Refund R-123", "content": "Refund approved by authorized manager for order 123."})
    assert r.status_code == 201
    cid = add_conversation(client, headers, "R001", *REFUND)
    body = evaluate(client, headers, cid)  # no evidence passed - DB record must be used
    assert body["evidence_assessment"] == "verified"
    assert not any(i["category"] == "hallucination" for i in body["issues"])


def test_evidence_isolation_and_delete(client):
    ha = make_business(client, "Biz A")
    hb = make_business(client, "Biz B")
    eid = client.post("/api/v1/evidence", headers=ha, json={
        "topic": "Order 1", "content": "Order 1 delivered on 2026-11-01."}).json()["id"]
    assert client.get("/api/v1/evidence", headers=hb).json() == []
    assert client.delete(f"/api/v1/evidence/{eid}", headers=hb).status_code == 404
    assert client.delete(f"/api/v1/evidence/{eid}", headers=ha).json()["deleted"] is True


def test_policy_survives_in_issue_after_policy_deleted(client):
    headers = make_business(client)
    pid = client.post("/api/v1/policies", headers=headers, json=REFUND_POLICY).json()["id"]
    cid = add_conversation(client, headers, "R001", *REFUND)
    body = evaluate(client, headers, cid)
    client.delete(f"/api/v1/policies/{pid}", headers=headers)
    stored = client.get(f"/api/v1/evaluations/{body['id']}", headers=headers).json()
    pv = [i for i in stored["issues"] if i["category"] == "policy_violation"]
    assert pv and pv[0]["policy_title"] == "Refund approval reserved"  # snapshot kept


def test_delivery_promise_rule_does_not_flag_past_delivery_statement():
    # The rule bans promising future dates - "your order is delivered" is a
    # (claims-layer) statement about the past, not a promise. Regression test
    # for a false positive caught in live verification of Phase 4.
    rule = "The chatbot must not promise unconfirmed delivery dates or guaranteed delivery timelines."
    assert check_policies("Your order is delivered.", [rule]) == []
    assert check_policies("Your order will be delivered within 2 days.", [rule]) != []
