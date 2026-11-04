# TrustOps AI
LLM Evaluation, Monitoring & Reliability Platform

TrustOps AI checks whether a business's chatbot / AI agent gives correct,
safe, relevant and policy-compliant answers. It does NOT replace the chatbot -
it independently monitors it, flags incorrect / unsupported / risky answers,
explains why, and suggests a safer reply.

## Current status: Phase 2 - Conversation Ingestion (complete, tested)
Working: FastAPI app, config, logging, `GET /` and `GET /health`; SQLAlchemy DB (SQLite, PostgreSQL-ready);
API-key auth with business-level isolation; conversation ingestion via REST, CSV upload, JSON upload and webhooks,
with duplicate protection and per-record error reporting. Tests: 16/16 passing.
Not yet built (honest scope): evaluation engine (Phase 3),
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
Endpoints: `POST /api/v1/businesses` · `POST|GET /api/v1/conversations` · `GET /api/v1/conversations/{id}` ·
`POST /api/v1/conversations/upload` (CSV) · `POST /api/v1/conversations/upload-json` · `POST /api/v1/webhooks/conversations`

## Test it
```powershell
pytest -v
```
Expected: 16 passed (Phase 1: root/health/404; Phase 2: auth, isolation, CSV/JSON import counts, duplicates, webhook idempotency).

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
