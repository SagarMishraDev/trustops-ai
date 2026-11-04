"""Benchmark runner + metric computation.

Ground truth comes from the labeled dataset. The engine's prediction for
a case is 'problem' when its status is flagged or needs_review, 'ok' when
passed. Metrics are the standard classification formulas - computed here,
never typed in by hand:

    precision = TP / (TP + FP)     recall = TP / (TP + FN)
    F1 = 2PR / (P + R)             accuracy = (TP + TN) / total

Runs use run_pipeline directly (no DB writes for cases), so benchmarking
never pollutes the business's real conversations.
"""
import json
from pathlib import Path
from app.evaluation.evaluators import get_evaluator
from app.evaluation.prompts import PROMPT_VERSION
from app.models.benchmark import BenchmarkRun
from app.services.evaluation import run_pipeline

DATASET_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "benchmark_dataset.json"


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def compute_metrics(tp: int, fp: int, tn: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1_score": round(f1, 4), "accuracy": round(accuracy, 4)}


def run_benchmark(db, business, prompt_version_label: str | None = None,
                  prompt_content: str | None = None) -> BenchmarkRun:
    dataset = load_dataset()
    evaluator = get_evaluator(prompt_content)
    label = prompt_version_label or PROMPT_VERSION
    tp = fp = tn = fn = 0
    details = []
    latencies = []
    total_cost = 0.0
    cat_checked = cat_hit = 0
    model_name = evaluator.name
    for case_ in dataset["cases"]:
        r = run_pipeline(case_["user_message"], case_["assistant_response"],
                         case_.get("policies") or [], case_.get("evidence"), evaluator=evaluator)
        predicted_problem = r["status"] in ("flagged", "needs_review")
        expected_problem = case_["expected"] == "problem"
        if predicted_problem and expected_problem:
            tp += 1; outcome = "true_positive"
        elif predicted_problem and not expected_problem:
            fp += 1; outcome = "false_positive"
        elif not predicted_problem and expected_problem:
            fn += 1; outcome = "false_negative"
        else:
            tn += 1; outcome = "true_negative"
        detected = sorted({i.category for i in r["issues"]})
        if expected_problem and case_.get("expected_categories"):
            cat_checked += 1
            if set(case_["expected_categories"]) & set(detected):
                cat_hit += 1
        latencies.append(r["latency_ms"])
        total_cost += r["estimated_cost"]
        details.append({
            "case_id": case_["id"], "group": case_["group"],
            "expected": case_["expected"], "predicted": "problem" if predicted_problem else "ok",
            "outcome": outcome, "score": r["overall_score"], "status": r["status"],
            "expected_categories": case_.get("expected_categories") or [],
            "detected_categories": detected, "latency_ms": r["latency_ms"],
        })
    metrics = compute_metrics(tp, fp, tn, fn)
    run = BenchmarkRun(
        business_id=business.id, dataset_name=dataset["name"],
        prompt_version_label=label, evaluation_model=model_name,
        total_cases=len(dataset["cases"]), true_positives=tp, false_positives=fp,
        true_negatives=tn, false_negatives=fn, **metrics,
        category_detection_rate=round(cat_hit / cat_checked, 4) if cat_checked else 0.0,
        average_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        total_estimated_cost=round(total_cost, 6),
        details=json.dumps(details),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
