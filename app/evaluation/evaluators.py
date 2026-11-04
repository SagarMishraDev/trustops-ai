"""Evaluators: who produces the judgment issues.

Two implementations behind ONE interface (invoke(dict) -> EvaluationResultSchema):

1. MockEvaluator (default, LLM_PROVIDER=mock) - an LCEL RunnableLambda that
   applies judgment-style heuristics. It is honestly named 'mock': it lets
   the whole platform run, demo and test with ZERO API cost and no key,
   but it is not an LLM and never claims to be.
2. LLMEvaluator - a real LCEL chain: ChatPromptTemplate | ChatModel | parser.
   The provider is chosen by env (openai / any OpenAI-compatible base URL
   such as Inception/Mercury). Invalid model output raises; the
   orchestrator catches it and falls back safely - garbage is never saved.

Cost estimate: rough chars/4 token estimate x configured per-1K rates.
It is an ESTIMATE - labelled as such everywhere it is shown.
"""
import json
from langchain_core.runnables import RunnableLambda
from app.core.config import get_settings
from app.evaluation.prompts import build_prompt
from app.schemas.evaluation import EvaluationResultSchema, IssueSchema


class EvaluatorConfigError(RuntimeError):
    pass


# ---------------- Mock ----------------
def _mock_judge(inputs: dict) -> EvaluationResultSchema:
    """Judgment-style heuristics for the mock evaluator: context consistency
    and a safer suggested reply for the classic failure shapes."""
    user = inputs["user_message"].lower()
    resp = inputs["assistant_response"]
    low = resp.lower()
    issues: list[IssueSchema] = []
    suggested = None
    if "refund" in low and ("approved" in low or "processed" in low):
        suggested = ("Your refund request has been received. Our team will review it "
                     "and update you once a decision is made.")
    elif "delivered" in low and "order" in user:
        suggested = ("Let me check the latest status of your order and confirm "
                     "the delivery details for you.")
    return EvaluationResultSchema(
        issues=issues,
        evidence_assessment=inputs.get("_claim_assessment", "unverified"),
        suggested_reply=suggested,
    )


class MockEvaluator:
    name = "mock-evaluator-v1"

    def __init__(self):
        self.chain = RunnableLambda(_mock_judge)

    def invoke(self, inputs: dict) -> EvaluationResultSchema:
        return self.chain.invoke(inputs)

    def estimate_cost(self, inputs: dict, result: EvaluationResultSchema) -> float:
        return 0.0


# ---------------- Real LLM (LCEL) ----------------
class LLMEvaluator:
    def __init__(self, llm, model_name: str):
        self.name = model_name
        self._llm = llm
        self.chain = build_prompt() | llm

    def invoke(self, inputs: dict) -> EvaluationResultSchema:
        message = self.chain.invoke({
            "policies": "\n".join(f"- {p}" for p in inputs.get("policies", [])) or "No policies provided.",
            "evidence": inputs.get("evidence") or "No evidence provided.",
            "user_message": inputs["user_message"],
            "assistant_response": inputs["assistant_response"],
        })
        text = getattr(message, "content", str(message))
        return parse_llm_output(text)

    def estimate_cost(self, inputs: dict, result: EvaluationResultSchema) -> float:
        settings = get_settings()
        in_tokens = (len(inputs["user_message"]) + len(inputs["assistant_response"])) / 4
        out_tokens = 300  # typical structured verdict size - an estimate, not a meter reading
        return round((in_tokens / 1000) * settings.llm_input_cost_per_1k
                     + (out_tokens / 1000) * settings.llm_output_cost_per_1k, 6)


def parse_llm_output(text: str) -> EvaluationResultSchema:
    """Validate raw LLM text into the schema. Raises ValueError on garbage:
    fenced code blocks are tolerated, free text is not."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("{"):]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM output contained no JSON object")
    data = json.loads(cleaned[start:end + 1])
    return EvaluationResultSchema.model_validate(data)


def get_evaluator():
    """Factory - picks the evaluator from configuration, fails loudly with
    a readable message when a real provider is chosen but misconfigured."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockEvaluator()
    if provider in ("openai", "openai_compatible", "inception", "mercury"):
        if not settings.llm_api_key:
            raise EvaluatorConfigError(
                f"LLM_PROVIDER={provider} but LLM_API_KEY is not set. "
                "Add it to your .env file (never paste keys in chat), or set LLM_PROVIDER=mock."
            )
        from langchain_openai import ChatOpenAI
        kwargs = {"model": settings.llm_model, "api_key": settings.llm_api_key,
                  "temperature": settings.llm_temperature}
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        return LLMEvaluator(ChatOpenAI(**kwargs), model_name=settings.llm_model)
    raise EvaluatorConfigError(f"Unknown LLM_PROVIDER '{provider}'. Use mock or openai.")
