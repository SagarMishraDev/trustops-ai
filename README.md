# TrustOps AI
LLM Evaluation, Monitoring & Reliability Platform

TrustOps AI checks whether a business's chatbot / AI agent gives correct,
safe, relevant and policy-compliant answers. It does NOT replace the chatbot -
it independently monitors it, flags incorrect / unsupported / risky answers,
explains why, and suggests a safer reply.

## Current status: COMPLETE — all 8 phases built, tested and documented
Working: FastAPI app, config, logging, `GET /` and `GET /health`; SQLAlchemy DB (SQLite, PostgreSQL-ready);
API-key auth with business-level isolation; conversation ingestion via REST, CSV upload, JSON upload and webhooks,
with duplicate protection and per-record error reporting. Phase 3 adds the evaluation engine:
deterministic checks (sensitive data, unsupported claims, relevance, completeness) + a LangChain/LCEL
evaluator (mock by default; real LLM via env config), deterministic scoring, risk levels, suggested
replies, human-review flags - all stored in the DB with model + prompt version. Tests: 31/31 passing.
Phase 4 adds policy management (CRUD, enable/disable, 5 one-click presets) - enabled policies are
applied automatically to every evaluation, each violation records which policy fired, and company
evidence records are checked automatically so supported claims become 'verified'. Tests: 43/43 passing.
Phase 5 adds: analytics APIs computed from the real DB (overview, issue distribution, 14-day trends),
a human review queue (decisions stored separately - the AI evaluation is never edited), a settings
endpoint that never exposes key values, a one-click demo seed, and a SaaS dashboard served at
`/dashboard` (sidebar, KPI cards, Chart.js charts, conversation explorer with filters, evaluation
detail with review form, policy management, settings actions, dark/light theme). Tests: 51/51 passing.
Phase 6 adds: a 50-case hand-labeled benchmark (`benchmarks/benchmark_dataset.json`: 15 correct,
35 problems across unsupported claims, policy violations, sensitive data, irrelevant, incomplete and
contradictory responses), a runner that measures precision / recall / F1 / accuracy, category
detection, latency and cost from REAL engine outputs, prompt-version storage, run comparison, and a
Benchmarks page in the dashboard. **Measured result (mock evaluator): TP 32, FP 0, TN 15, FN 3 —
Precision 1.000, Recall 0.914, F1 0.955, Accuracy 0.940.** The only missed cases are the 3
contradictory ones: context-consistency judgment needs a real LLM, and the benchmark exists to prove
exactly that. (The benchmark also caught and fixed a real bug: Indian phone numbers written as
+91 98765 43210 were not detected.) Prompt comparison is honest: with the mock evaluator, different
prompts produce identical metrics and the API says so; prompts only change behaviour with a real LLM.
Run it yourself without the server: `python scripts/run_benchmark.py`.
Phase 7 hardening: (1) **Signed webhooks** - every business gets a webhook secret (`whsec_...`,
shown once at creation). Webhook senders must send `X-TrustOps-Timestamp` and
`X-TrustOps-Signature: sha256=<HMAC-SHA256(secret, "<timestamp>.<raw body>")>`. Tampered bodies and
wrong secrets get 401 `invalid_signature`; timestamps older than 5 minutes get 401 `stale_timestamp`
(replay protection). (2) **Rate limiting** - 120 requests/minute per API key (configurable), excess
gets 429 with `Retry-After`. Counters are in-memory per process; multi-instance deployments need
Redis (noted for production). (3) **Structured errors + request IDs** - every error body is
`{detail, error_code, request_id}` and every response carries `X-Request-ID`; security headers
(nosniff, DENY framing, no-referrer) are set on all responses.

Send a signed webhook (Python example):
```python
import hashlib, hmac, json, time, urllib.request
body = json.dumps({"conversation_id": "C1", "user_message": "Where is my order?",
                   "assistant_response": "Your order is delivered.",
                   "timestamp": "2026-11-04T10:30:00", "session_id": "S1"}).encode()
ts = str(int(time.time()))
sig = "sha256=" + hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
req = urllib.request.Request(URL, data=body, method="POST", headers={
    "X-API-Key": API_KEY, "X-TrustOps-Timestamp": ts, "X-TrustOps-Signature": sig,
    "Content-Type": "application/json"})
```
Phase 8 (final): Dockerfile (non-root, healthcheck, migrations-then-serve) and
docker-compose with PostgreSQL 16; Alembic migrations own the production schema — the initial
migration was generated from the models and VERIFIED by applying it to a real PostgreSQL 16 and
running the full golden path against it (seed avg 52.5, benchmark F1 0.9552 — identical to SQLite).
Post-deploy smoke test: `BASE_URL=... python scripts/smoke_test.py` (7 checks). Docs:
`docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`. Honest limits that remain: Docker itself could not be
run inside the build sandbox (no Docker daemon) — the compose file is YAML-validated and every
non-Docker step (migrations, app boot, smoke path) was executed for real against PostgreSQL;
contradiction detection needs a real LLM (benchmark FN=3 by design); rate limiting is per-process
memory until Redis is added for multi-instance deployments; cost figures are estimates.

## Tech stack
Python 3.11+, FastAPI, Uvicorn, Pydantic, python-dotenv.
Later phases: LangChain/LCEL, SQLAlchemy + SQLite (PostgreSQL-ready), Chart.js dashboard, Pytest, Docker.

## Run it (Windows / PowerShell)
```powershell
cd trustops-ai
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```
Open http://127.0.0.1:8000/ , http://127.0.0.1:8000/health , http://127.0.0.1:8000/docs

## Phase 2 API - quick try
```powershell
# 1) Create a business - the API key is shown ONLY once, save it
curl -X POST http://127.0.0.1:8000/api/v1/businesses -H "Content-Type: application/json" -d '{\"name\":\"Demo\"}'
# 2) Upload the sample CSV (use your key)
curl -X POST http://127.0.0.1:8000/api/v1/conversations/upload -H "X-API-Key: tok_YOUR_KEY" -F "file=@samples/sample_conversations.csv"
# -> {"imported":3,"duplicates_skipped":0,"failed":0,"errors":[]}  (upload again -> duplicates_skipped:3)
# 3) List what was stored
curl http://127.0.0.1:8000/api/v1/conversations -H "X-API-Key: tok_YOUR_KEY"
```
## Phase 3 - evaluate conversations
```powershell
# Evaluate one conversation (internal id from the list endpoint). Policies are optional rule texts.
curl -X POST http://127.0.0.1:8000/api/v1/evaluations -H "X-API-Key: tok_YOUR_KEY" -H "Content-Type: application/json" -d '{\"conversation_id\":2,\"policies\":[\"Only authorized staff can approve refunds.\"]}'
# -> the sample refund conversation scores 30, status flagged, risk high, with a suggested safer reply
# Evaluate everything at once:
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/bulk -H "X-API-Key: tok_YOUR_KEY" -H "Content-Type: application/json" -d '{}'
```
How scoring works (deterministic, explainable): each issue costs points by severity
(critical 50, high 35, medium 20, low 10) from 100. Any high/critical issue -> flagged + human review.
A claim with no evidence is **unsupported** - never labelled false, never verified.
Real LLM: set `LLM_PROVIDER=openai` (or an OpenAI-compatible base URL) and `LLM_API_KEY` in your `.env`.

## Phase 4 - policies & evidence
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/policies/presets/apply -H "X-API-Key: tok_YOUR_KEY"   # 5 starter policies
curl -X POST http://127.0.0.1:8000/api/v1/policies -H "X-API-Key: tok_YOUR_KEY" -H "Content-Type: application/json" -d '{\"title\":\"No discount promises\",\"rule_text\":\"The chatbot must never offer discounts without manager approval.\"}'
curl -X POST http://127.0.0.1:8000/api/v1/evidence -H "X-API-Key: tok_YOUR_KEY" -H "Content-Type: application/json" -d '{\"topic\":\"Order 123\",\"content\":\"Order delivered and confirmed by courier.\"}'
```
From now on you do NOT pass policies/evidence in evaluation requests - the system loads your
business's enabled policies and evidence records itself. Policy engine rule: a policy fires only
when it is prohibitive ("must not/never/only authorized/escalate"), shares a topic with the
response (refund, delivery, medical, discount, credentials, personal data...), and the response
makes a definitive statement/promise on that topic. "Do not promise dates" rules fire only on
future promises, not on statements about the past (those are checked against evidence instead).

## Phase 5 - use the dashboard
```powershell
uvicorn app.main:app --reload --port 8000
# open http://127.0.0.1:8000/dashboard
# -> click "Create demo workspace (1 click)": makes a business, applies presets,
#    seeds 8 marked DEMO conversations and evaluates them with the real engine.
#    Expected overview: 8 conversations, 1 passed, 7 flagged, avg score 52.5, 7 pending reviews.
```
Review rule: submitting a review (confirmed / false positive) appends a HumanReview record.
The original evaluation row is never modified - both judgments stay on record.

Endpoints: `POST /api/v1/businesses` · `POST|GET /api/v1/conversations` · `GET /api/v1/conversations/{id}` ·
`POST /api/v1/conversations/upload` (CSV) · `POST /api/v1/conversations/upload-json` · `POST /api/v1/webhooks/conversations`

## Test it
```powershell
pytest -v
```
Expected: 69 passed — the full suite across all 8 phases (ingestion, evaluation engine, policy & evidence, dashboard & reviews, benchmark, hardening, deployment assets).

## Project structure
```
trustops-ai/
  app/
    main.py            # FastAPI entry point
    core/config.py     # env-based settings (no hard-coded secrets)
    core/logging_config.py
    api/v1/health.py   # /health route
  tests/test_phase1.py
  data/                # local SQLite DB will live here (Phase 2+)
  requirements.txt
  .env.example
  PROGRESS.md
```
