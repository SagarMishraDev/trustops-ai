# TrustOps AI — Architecture

## What the system does
TrustOps AI evaluates conversations produced by OTHER chatbots. It never
answers end-users itself. For every conversation it answers one question:
"Was this response safe and correct — and can we prove why we think so?"

## Component map
```
Chatbot systems (any vendor)
    |  REST / CSV / JSON upload / signed webhook (HMAC-SHA256)
    v
FastAPI app -------------------------------------------------+
  middleware: request-id, security headers, rate limiting    |
  api/v1: businesses, conversations, webhooks, evaluations,  |
          policies, evidence, reviews, analytics, benchmarks,|
          system (settings, demo seed)                       |
  services: ingestion, evaluation (pipeline), benchmark      |
  evaluation/: deterministic checks, policy engine,          |
               LangChain evaluators (mock | OpenAI-compatible)|
  dashboard: static HTML/CSS/JS + Chart.js served at /dashboard
    |
    v
SQLAlchemy -> SQLite (dev) | PostgreSQL (production, Alembic-owned)
```

## The evaluation pipeline (single source of truth: `run_pipeline`)
1. **Deterministic checks first** — credential/OTP requests, PII patterns
   (email, phone incl. Indian formats, long digit runs), action claims,
   relevance overlap, completeness, prompt-injection patterns in the
   USER message, and the policy engine (enabled business policies +
   evidence records are auto-loaded).
2. **Claim verdicts are evidence-based, three-state only:** `verified`
   (evidence supports it), `unsupported` (no evidence), `unverified`
   (no claim detected). A claim is never called "false" without proof.
3. **Evaluator (LLM or mock)** adds judgment issues through a strict
   Pydantic contract; malformed output is rejected and the pipeline
   falls back to deterministic results, honestly labelled.
4. **Scoring is deterministic, never the LLM's opinion:** critical 50,
   high 35, medium 20, low 10 deducted from 100; high+ issues flag the
   conversation and queue it for human review.
5. Conversation text is treated as **untrusted data** in prompts
   (injection safety), and the prompt version + model name are stored
   on every evaluation for auditability.

## Human review
Reviewers confirm or mark false positives in a SEPARATE table — the AI's
original evaluation is never edited, so false-positive rate stays
measurable forever.

## Benchmarking
50 hand-labeled cases are the ground truth. Precision/recall/F1 are
computed from real engine outputs; every run stores per-case outcomes so
misses (currently: contradiction detection, which needs a real LLM) stay
visible instead of being averaged away.

## Security model
- API keys: random, stored only as SHA-256 hashes, shown once.
- Tenant isolation on every query; cross-tenant ids return 404.
- Webhooks: HMAC-SHA256 signature over `<timestamp>.<body>`, 5-minute
  replay window, per-business secret (shown once, never in GETs).
- Rate limiting per API key (429 + Retry-After), structured errors with
  request IDs, security headers on all responses.
- Secrets only via environment variables; `.env` is git-ignored.

## Known limits (honest)
- Contradiction/context judgment needs a real LLM; with the mock
  evaluator those benchmark cases are missed by design.
- Rate-limit counters are per-process memory — use Redis when running
  multiple instances.
- Cost figures are estimates from configured per-1K rates, not billing.
- Alembic owns the production schema; `create_all` remains only as a
  local-dev convenience.
