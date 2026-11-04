# TrustOps AI - production image
# Uses python -m uvicorn (never the bare console script) so the image works
# regardless of how the venv/site-packages were laid out at build time.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2-binary are bundled in the wheel; curl is only
# for the container healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY benchmarks ./benchmarks
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

# Run as a non-root user
RUN useradd --create-home trustops && mkdir -p /app/data && chown -R trustops:trustops /app
USER trustops

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

# Migrations first (idempotent), then the server. create_all in the app is
# a dev convenience; in this image Alembic owns the schema.
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
