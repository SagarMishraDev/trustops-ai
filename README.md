# TrustOps AI
LLM Evaluation, Monitoring & Reliability Platform

TrustOps AI checks whether a business's chatbot / AI agent gives correct,
safe, relevant and policy-compliant answers. It does NOT replace the chatbot -
it independently monitors it, flags incorrect / unsupported / risky answers,
explains why, and suggests a safer reply.

## Current status: Phase 1 - Foundation (complete, tested)
Working: FastAPI app, environment-based config, logging, `GET /` and `GET /health`, tests.
Not yet built (honest scope): ingestion (Phase 2), evaluation engine (Phase 3),
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

## Test it
```powershell
pytest -v
```
Expected: 3 passed (root, health, 404 handling).

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
