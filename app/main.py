"""TrustOps AI - FastAPI application entry point.

Run from the project root (trustops-ai folder):
    uvicorn app.main:app --reload --port 8000

Open: /  (root) | /health | /docs (Swagger)
Phase 2 adds: /api/v1/businesses, /api/v1/conversations (+ /upload,
/upload-json), /api/v1/webhooks/conversations - all behind X-API-Key.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app import __version__
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.core.rate_limit import FixedWindowRateLimiter
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
from app.api.v1.benchmarks import router as benchmarks_router

settings = get_settings()
logger = setup_logging(debug=settings.debug)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="LLM evaluation, monitoring and reliability platform.",
    )
    init_db()
    app.state.rate_limiter = FixedWindowRateLimiter(settings.rate_limit_per_minute)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)  # added last = outermost

    _ERROR_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden",
                    404: "not_found", 405: "method_not_allowed", 409: "conflict",
                    413: "payload_too_large", 422: "validation_error",
                    429: "rate_limited", 503: "service_unavailable", 500: "internal_error"}

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={
            "detail": exc.detail,
            "error_code": _ERROR_CODES.get(exc.status_code, "http_error"),
            "request_id": getattr(request.state, "request_id", None),
        })

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(status_code=422, content={
            "detail": "Request validation failed",
            "error_code": "validation_error",
            "errors": jsonable_encoder(exc.errors()),
            "request_id": getattr(request.state, "request_id", None),
        })

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={
            "detail": "Internal server error",
            "error_code": "internal_error",
            "request_id": getattr(request.state, "request_id", None),
        })

    @app.get("/", tags=["health"])
    def root():
        return {
            "name": settings.app_name,
            "version": __version__,
            "status": "running",
            "docs": "/docs",
            "health": "/health",
            "phase": "Phase 7 - Live Integration Hardening",
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
    app.include_router(benchmarks_router)
    logger.info("%s v%s started (env=%s)", settings.app_name, settings.app_version, settings.environment)
    return app


app = create_app()
