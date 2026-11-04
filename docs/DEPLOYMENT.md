# TrustOps AI — Deployment Guide

## Option A: Docker Compose (recommended)
```bash
git clone https://github.com/SagarMishraDev/trustops-ai.git
cd trustops-ai
# optional: create .env to override the dev defaults, e.g.
#   POSTGRES_PASSWORD=<strong password>
#   LLM_PROVIDER=openai  LLM_API_KEY=<key>  LLM_MODEL=<model>
docker compose up --build
```
Then open **http://localhost:8000/dashboard** and click
"Create demo workspace (1 click)".
The app container runs `alembic upgrade head` before starting Uvicorn,
and waits for PostgreSQL to be healthy first. Data persists in the
`trustops_pgdata` volume.

## Option B: Local Python (development)
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # edit values if needed
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
SQLite is used by default (`DATABASE_URL` unset). For PostgreSQL, set
`DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname` and run
`alembic upgrade head` once.

## Verify any deployment
```bash
BASE_URL=http://localhost:8000 python scripts/smoke_test.py
```
Expect 7 PASS lines (health, business, seed, analytics, signed webhook,
unsigned rejection, benchmark).

## Environment variables
| Variable | Default | Purpose |
|---|---|---|
| DATABASE_URL | sqlite:///./data/trustops.db | SQLAlchemy URL (PostgreSQL in production) |
| ENVIRONMENT | development | deployment label |
| DEBUG | true | verbose logging |
| LLM_PROVIDER | mock | mock, or any OpenAI-compatible provider id |
| LLM_MODEL | mock-evaluator-v1 | model name for the evaluator |
| LLM_API_KEY | (empty) | provider key — set in the platform console, never in code |
| LLM_BASE_URL | (empty) | provider base URL for OpenAI-compatible APIs |
| RATE_LIMIT_PER_MINUTE | 120 | per-API-key request budget |
| WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS | 300 | signed-webhook replay window |
| MAX_UPLOAD_SIZE_MB | 10 | CSV/JSON upload cap |

## Go-live checklist
- [ ] Strong POSTGRES_PASSWORD (not the compose dev default)
- [ ] Real LLM provider + key set in the platform's env console (optional; mock works)
- [ ] HTTPS in front of the app (platform/reverse proxy) — webhook secrets travel in headers' signatures, API keys in headers
- [ ] `python scripts/smoke_test.py` green against the public URL
- [ ] Backups scheduled for the PostgreSQL volume
- [ ] If scaling beyond 1 instance: move rate limiting to Redis first
