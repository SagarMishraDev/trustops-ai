"""TrustOps AI - FastAPI application entry point.

Run from the project root (trustops-ai folder):
    uvicorn app.main:app --reload --port 8000

Then open:
    http://127.0.0.1:8000/         -> root info
    http://127.0.0.1:8000/health  -> health check
    http://127.0.0.1:8000/docs    -> interactive API docs (Swagger)
"""
from fastapi import FastAPI
from app import __version__
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.api.v1.health import router as health_router

settings = get_settings()
logger = setup_logging(debug=settings.debug)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="LLM evaluation, monitoring and reliability platform. "
                    "Evaluates chatbot/agent conversations for correctness, "
                    "hallucination risk, policy violations and sensitive-data exposure.",
    )

    @app.get("/", tags=["health"])
    def root():
        return {
            "name": settings.app_name,
            "version": __version__,
            "status": "running",
            "docs": "/docs",
            "health": "/health",
            "phase": "Phase 1 - Foundation",
        }

    app.include_router(health_router)
    # Phase 2+ routers will be included here (conversations, evaluations, ...)
    logger.info("%s v%s started (env=%s)", settings.app_name, settings.app_version, settings.environment)
    return app


app = create_app()
