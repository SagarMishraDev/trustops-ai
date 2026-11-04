# TrustOps AI
LLM Evaluation, Monitoring & Reliability Platform

TrustOps AI checks whether a business's chatbot / AI agent gives correct,
safe, relevant and policy-compliant answers. It does NOT replace the chatbot -
it independently monitors it, flags incorrect / unsupported / risky answers,
explains why, and suggests a safer reply.

## Current status: Phase 4 - Policy & Evidence Engine (complete, tested)
Working: FastAPI app, config, logging, `GET /` and `GET /health`; SQLAlchemy DB (SQLite, PostgreSQL-ready);
API-key auth with business-level isolation; conversation ingestion via REST, CSV upload, JSON upload and webhooks,
with duplicate protection and per-record error reporting. Phase 3 adds the evaluation engine:
deterministic checks (sensitive data, unsupported claims, relevance, completeness) + a LangChain/LCEL
evaluator (mock by default; real LLM via env config), deterministic scoring, risk levels, suggested
replies, human-review flags - all stored in the DB with model + prompt version. Tests: 31/31 passing.
Phase 4 adds policy management (CRUD, enable/disable, 5 one-click presets) - enabled policies are
applied automatically to every evaluation, each violation records which policy fired, and company
evidence records are checked automatically so supported claims become 'verified'. Tests: 43/43 passing.
Not yet built (honest scope): dashboard UI (Phase 5),
policies (Phase 4), dashboard (Phase 5), benchmark (Phase 6), webhooks (Phase 7),
Docker deployment (Phase 8).

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

Endpoints: `POST /api/v1/businesses` · `POST|GET /api/v1/conversations` · `GET /api/v1/conversations/{id}` ·
`POST /api/v1/conversations/upload` (CSV) · `POST /api/v1/conversations/upload-json` · `POST /api/v1/webhooks/conversations`

## Test it
```powershell
pytest -v
```
Expected: 43 passed (Phases 1-3 plus Phase 4: policy CRUD/presets/isolation, generalized policy engine, disabled-policy skip, evidence auto-verify, policy snapshot surviving deletion).

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
