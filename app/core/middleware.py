"""HTTP middleware: request IDs, security headers, rate limiting.

Every response carries X-Request-ID so a user report ("it failed at
6:40pm") can be matched to one exact request in the logs. Every error
body carries the same id (see the exception handlers in main.py).
"""
import hashlib
import uuid
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Only API traffic is limited; business registration is exempt
        # (it is the entry door - production deployments gate it with
        # infra-level controls), and static/dashboard/health stay open.
        if not path.startswith("/api/") or (path == "/api/v1/businesses" and request.method == "POST"):
            return await call_next(request)
        limit = getattr(request.app.state, "rate_limit_per_minute", None) or get_settings().rate_limit_per_minute
        request.app.state.rate_limiter.limit = limit
        api_key = request.headers.get("x-api-key")
        if api_key:
            key = "key:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]
        else:
            key = "ip:" + (request.client.host if request.client else "unknown")
        ok, retry_after = request.app.state.rate_limiter.allow(key)
        if not ok:
            return JSONResponse(status_code=429, content={
                "detail": "Rate limit exceeded. Slow down and retry after the window resets.",
                "error_code": "rate_limited",
                "request_id": getattr(request.state, "request_id", None),
            }, headers={"Retry-After": str(retry_after)})
        return await call_next(request)
