"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.auth import require_admin_api_key
from app.core.config import get_settings
from app.core.database import cleanup_old_logs, init_db
from app.middleware.rate_limit import RateLimitMiddleware, create_rate_limit_store
from app.routers import analytics, chat, health
from app.services.guardrails import GuardrailError

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting LLM Gateway API...")
    await init_db()
    try:
        await cleanup_old_logs(settings.log_retention_days)
    except Exception as e:  # pragma: no cover - startup resilience
        logger.warning("Skipping startup log cleanup: %s", type(e).__name__)
    logger.info("Database initialized")
    yield
    logger.info("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="LLM Gateway API",
    description="Enterprise-grade LLM gateway with input validation and request logging",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default Swagger UI
    redoc_url="/redoc" if settings.enable_docs and not settings.protected_paths else None,
    # Keep OpenAPI available for custom /docs page even in protected mode.
    openapi_url="/openapi.json" if settings.enable_openapi else None,
)

@app.get("/docs", include_in_schema=False, dependencies=[Depends(require_admin_api_key)])
async def custom_swagger_ui_html():
    if not settings.enable_docs:
        raise HTTPException(status_code=404, detail="Documentation is disabled.")
    return FileResponse("static/docs.html")


# Security headers middleware
# Moderate CSP v1: allowlists the three CDNs the app actually pulls from.
# 'unsafe-inline' on script-src is needed because the analytics dashboard inlines
# its Chart.js bootstrap. A nonce-based tightening is a follow-up.
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://unpkg.com; "
    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = CSP_POLICY
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies larger than configured limit."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body is too large.", "error_type": "request_too_large"},
            )
        return await call_next(request)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Admin-API-Key"],
)

# Add rate limiting middleware
rate_limit_store = create_rate_limit_store(settings.redis_url)
app.add_middleware(
    RateLimitMiddleware,
    store=rate_limit_store,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


@app.exception_handler(GuardrailError)
async def guardrail_exception_handler(request: Request, exc: GuardrailError):
    """Handle guardrail violations."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_type": exc.error_type,
        },
    )


# Include routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(analytics.router)

# Mount static files (must be last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
