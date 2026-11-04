"""Evaluation orchestrator.

FLOW: deterministic checks -> evaluator (mock/LLM) -> merge + dedupe ->
deterministic scoring -> persist Evaluation + Issues.

SCORING IS DETERMINISTIC ON PURPOSE: an LLM may describe issues, but the
final score is computed here from issue severities with fixed weights.
Same issues = same score, no matter which model described them.
  weights: critical 50, high 35, medium 20, low 10 (score = 100 - sum, min 0)
  status:  any high/critical issue or score < 50 -> flagged (+ human review)
           score < 80 -> needs_review (+ human review)
           otherwise -> passed
"""
import time
from sqlalchemy.orm import Session
from app.evaluation import deterministic
from app.evaluation.evaluators import EvaluatorConfigError, MockEvaluator, get_evaluator
from app.evaluation.prompts import PROMPT_VERSION
from app.models.conversation import Conversation
from app.models.evaluation import Evaluation, EvaluationIssue
from app.schemas.evaluation import EvaluationResultSchema, IssueSchema

SEVERITY_WEIGHTS = {"critical": 50, "high": 35, "medium": 20, "low": 10}
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _merge(issues: list[IssueSchema]) -> list[IssueSchema]:
    """Dedupe by (category, first 50 chars of reason), keep highest severity."""
    best: dict[tuple, IssueSchema] = {}
    for issue in issues:
        key = (issue.category, issue.reason[:50].lower())
        if key not in best or SEVERITY_ORDER[issue.severity] > SEVERITY_ORDER[best[key].severity]:
            best[key] = issue
    return sorted(best.values(), key=lambda i: -SEVERITY_ORDER[i.severity])


def _score_and_status(issues: list[IssueSchema]) -> tuple[int, str, str, bool]:
    score = max(0, 100 - sum(SEVERITY_WEIGHTS[i.severity] for i in issues))
    worst = max((SEVERITY_ORDER[i.severity] for i in issues), default=-1)
    risk = {-1: "low", 0: "low", 1: "medium", 2: "high", 3: "critical"}[worst]
    if worst >= 2 or score < 50:
        return score, "flagged", risk, True
    if score < 80:
        return score, "needs_review", risk, True
    return score, "passed", risk, False


def run_pipeline(user_message: str, assistant_response: str,
                 policies: list | None = None, evidence: str | None = None,
                 evaluator=None) -> dict:
    """The full evaluation pipeline WITHOUT any database access.

    This is the single source of truth used by both the live orchestrator
    (which persists results) and the Phase 6 benchmark runner (which must
    not pollute the production tables with benchmark conversations).
    Returns a plain dict: issues, score, status, risk, review flag,
    assessment, suggested reply, model, latency, cost, injection flag.
    """
    policies = policies or []
    start = time.perf_counter()

    det_issues, claim_assessment, injection = deterministic.run_deterministic_checks(
        user_message, assistant_response, policies, evidence)

    if evaluator is None:
        evaluator = get_evaluator()  # may raise EvaluatorConfigError - API layer turns it into a clean 503
    inputs = {
        "user_message": user_message,
        "assistant_response": assistant_response,
        "policies": policies, "evidence": evidence,
        "_claim_assessment": claim_assessment,
    }
    fallback_note = None
    try:
        result: EvaluationResultSchema = evaluator.invoke(inputs)
        estimated_cost = evaluator.estimate_cost(inputs, result)
        model_name = evaluator.name
    except EvaluatorConfigError:
        raise
    except Exception:
        # Invalid LLM output / provider failure: fall back to deterministic
        # results only. The evaluation is still saved, honestly labelled.
        result = EvaluationResultSchema(evidence_assessment=claim_assessment)
        estimated_cost = 0.0
        model_name = f"{evaluator.name} (failed - deterministic fallback)"
        fallback_note = "The LLM evaluator returned unusable output, so this result uses deterministic checks only."

    issues = _merge(det_issues + [i.model_copy(update={"source": "mock" if isinstance(evaluator, MockEvaluator) else "llm"})
                                  for i in result.issues])
    if fallback_note:
        issues.append(IssueSchema(category="accuracy", severity="low", source="deterministic",
                                  reason=fallback_note, evidence=None, suggested_action=None))
        issues = _merge(issues)

    score, status, risk, review = _score_and_status(issues)
    assessment = claim_assessment if claim_assessment != "unverified" else result.evidence_assessment
    suggested = result.suggested_reply
    if not suggested and issues:
        top = issues[0]
        suggested = top.suggested_action

    latency_ms = int((time.perf_counter() - start) * 1000)
    return {
        "issues": issues, "overall_score": score, "status": status, "risk_level": risk,
        "human_review_required": review, "evidence_assessment": assessment,
        "suggested_reply": suggested, "evaluation_model": model_name,
        "latency_ms": latency_ms, "estimated_cost": estimated_cost,
        "prompt_injection_detected": injection,
    }


def evaluate_conversation(db: Session, conversation: Conversation,
                          policies: list | None = None,
                          evidence: str | None = None) -> Evaluation:
    r = run_pipeline(conversation.user_message, conversation.assistant_response,
                     policies, evidence)
    issues = r["issues"]
    ev = Evaluation(
        conversation_id=conversation.id, overall_score=r["overall_score"], status=r["status"],
        risk_level=r["risk_level"], evidence_assessment=r["evidence_assessment"],
        prompt_injection_detected=r["prompt_injection_detected"],
        suggested_reply=r["suggested_reply"], human_review_required=r["human_review_required"],
        evaluation_model=r["evaluation_model"], prompt_version=PROMPT_VERSION,
        latency_ms=r["latency_ms"], estimated_cost=r["estimated_cost"],
    )
    db.add(ev)
    db.flush()
    for issue in issues:
        db.add(EvaluationIssue(
            evaluation_id=ev.id, category=issue.category, severity=issue.severity,
            reason=issue.reason, evidence=issue.evidence,
            suggested_action=issue.suggested_action, source=issue.source,
            policy_id=issue.policy_id, policy_title=issue.policy_title,
        ))
    db.commit()
    db.refresh(ev)
    return ev
