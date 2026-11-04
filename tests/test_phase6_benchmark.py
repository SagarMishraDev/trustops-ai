"""Phase 6 tests: dataset integrity, metric math, runs, prompt versions, compare.

The benchmark numbers asserted here are the engine's REAL measured results
on this dataset (mock evaluator): TP=32 FP=0 TN=15 FN=3. The only missed
cases are the 3 contradictory ones - context-consistency judgment needs a
real LLM, and the benchmark exists to expose exactly that."""
from tests.conftest import make_business
from app.services.benchmark import compute_metrics, load_dataset


def test_dataset_integrity():
    ds = load_dataset()
    cases = ds["cases"]
    assert len(cases) == 50 and len({c["id"] for c in cases}) == 50
    groups = {c["group"] for c in cases}
    assert groups == {"correct", "unsupported_claim", "policy_violation", "sensitive",
                      "irrelevant", "incomplete", "contradictory"}
    assert sum(1 for c in cases if c["expected"] == "ok") == 15
    assert sum(1 for c in cases if c["expected"] == "problem") == 35
    for c in cases:
        assert c["user_message"] and c["assistant_response"] and c["expected"] in ("ok", "problem")


def test_compute_metrics_math():
    m = compute_metrics(tp=32, fp=0, tn=15, fn=3)
    assert m == {"precision": 1.0, "recall": 0.9143, "f1_score": 0.9552, "accuracy": 0.94}
    z = compute_metrics(0, 0, 0, 0)
    assert z["precision"] == 0.0 and z["f1_score"] == 0.0  # no division-by-zero lies


def test_spaced_phone_number_detected_regression():
    # Benchmark case B034 caught this: '+91 98765 43210' (5+5 spaced) was missed
    from app.evaluation.deterministic import check_sensitive_data
    issues = check_sensitive_data("You can call the delivery agent directly on +91 98765 43210.")
    assert any(i.category == "sensitive_information" for i in issues)


def test_benchmark_run_real_numbers(client):
    headers = make_business(client)
    r = client.post("/api/v1/benchmarks/run", headers=headers, json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["total_cases"] == 50
    assert (run["true_positives"], run["false_positives"], run["true_negatives"], run["false_negatives"]) == (32, 0, 15, 3)
    assert run["precision"] == 1.0 and run["recall"] == 0.9143
    assert run["f1_score"] == 0.9552 and run["accuracy"] == 0.94
    assert run["prompt_version_label"] == "eval-v1" and run["evaluation_model"] == "mock-evaluator-v1"
    assert run["total_estimated_cost"] == 0.0 and run["average_latency_ms"] >= 0
    missed = [d for d in run["details"] if d["outcome"] == "false_negative"]
    assert {d["case_id"] for d in missed} == {"B048", "B049", "B050"}
    assert all(d["group"] == "contradictory" for d in missed)
    assert run["category_detection_rate"] == 0.8857  # 31/35 labeled categories hit: the 3 contradictions miss, and 1 flagged case was caught under a different category than its label
    # benchmark runs must NOT pollute the real conversation tables
    assert client.get("/api/v1/conversations", headers=headers).json() == []


def test_prompt_versions_and_compare_honesty(client):
    headers = make_business(client)
    pv = client.post("/api/v1/prompt-versions", headers=headers, json={
        "name": "Strict evaluator", "version": "v2",
        "prompt_content": "You are a strict evaluator. Flag anything uncertain."})
    assert pv.status_code == 201
    base = client.post("/api/v1/benchmarks/run", headers=headers, json={}).json()
    alt = client.post("/api/v1/benchmarks/run", headers=headers,
                      json={"prompt_version_id": pv.json()["id"]}).json()
    assert alt["prompt_version_label"] == "Strict evaluator@v2"
    cmp_ = client.get(f"/api/v1/benchmarks/compare/{base['id']}/{alt['id']}", headers=headers).json()
    # with the mock evaluator the honest answer is: prompts change nothing
    assert cmp_["difference_b_minus_a"]["f1_score"] == 0.0
    assert "mock" in cmp_["note"].lower()


def test_benchmark_isolation(client):
    ha = make_business(client, "Biz A")
    hb = make_business(client, "Biz B")
    run = client.post("/api/v1/benchmarks/run", headers=ha, json={}).json()
    assert client.get("/api/v1/benchmarks", headers=hb).json() == []
    assert client.get(f"/api/v1/benchmarks/{run['id']}", headers=hb).status_code == 404
    assert client.post("/api/v1/benchmarks/run", headers=hb,
                       json={"prompt_version_id": 9999}).status_code in (404, 422)
