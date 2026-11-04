"""Run the benchmark from the terminal - no server needed.

Usage (from the project root):
    python scripts/run_benchmark.py

Uses the configured evaluator (mock by default). Prints real measured
metrics and every missed case, so weaknesses are visible, not hidden.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.evaluators import get_evaluator
from app.services.benchmark import compute_metrics, load_dataset
from app.services.evaluation import run_pipeline


def main() -> None:
    dataset = load_dataset()
    evaluator = get_evaluator()
    tp = fp = tn = fn = 0
    misses = []
    for case_ in dataset["cases"]:
        r = run_pipeline(case_["user_message"], case_["assistant_response"],
                         case_.get("policies") or [], case_.get("evidence"), evaluator=evaluator)
        predicted = r["status"] in ("flagged", "needs_review")
        expected = case_["expected"] == "problem"
        if predicted and expected:
            tp += 1
        elif predicted:
            fp += 1; misses.append((case_, "false positive"))
        elif expected:
            fn += 1; misses.append((case_, "false negative (missed problem)"))
        else:
            tn += 1
    m = compute_metrics(tp, fp, tn, fn)
    print(f"Dataset: {dataset['name']} ({len(dataset['cases'])} cases) | Evaluator: {evaluator.name}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Precision={m['precision']} Recall={m['recall']} F1={m['f1_score']} Accuracy={m['accuracy']}")
    if misses:
        print("\nMissed / wrong cases:")
        for case_, why in misses:
            print(f"  {case_['id']} [{case_['group']}] {why}: {case_['assistant_response'][:70]}")
    else:
        print("\nNo misses.")


if __name__ == "__main__":
    main()
