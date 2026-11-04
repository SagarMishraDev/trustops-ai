"""TrustOps AI - FastAPI application entry point.

Run from the project root (trustops-ai folder):
    uvicorn app.main:app --reload --port 8000

Open: /  (root) | /health | /docs (Swagger)
Phase 2 adds: /api/v1/businesses, /api/v1/conversations (+ /upload,
/upload-json), /api/v1/webhooks/conversations - all behind X-API-Key.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app import __version__
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.api.v1.health import router as health_router
from app.api.v1.businesses import router as businesses_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.evaluations import router as evaluations_router
from app.api.v1.policies import router as policies_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.system import router as system_router

settings = get_settings()
logger = setup_logging(debug=settings.debug)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="LLM evaluation, monitoring and reliability platform.",
    )
    init_db()

    @app.get("/", tags=["health"])
    def root():
        return {
            "name": settings.app_name,
            "version": __version__,
            "status": "running",
            "docs": "/docs",
            "health": "/health",
            "phase": "Phase 5 - Dashboard & Review Queue",
        }

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/dashboard", tags=["health"])
    def dashboard():
        return FileResponse(static_dir / "index.html")

    app.include_router(health_router)
    app.include_router(businesses_router)
    app.include_router(conversations_router)
    app.include_router(webhooks_router)
    app.include_router(evaluations_router)
    app.include_router(policies_router)
    app.include_router(evidence_router)
    app.include_router(reviews_router)
    app.include_router(analytics_router)
    app.include_router(system_router)
    logger.info("%s v%s started (env=%s)", settings.app_name, settings.app_version, settings.environment)
    return app


app = create_app()
