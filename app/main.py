"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import init_db
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
    redoc_url="/redoc",
)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return FileResponse("static/docs.html")


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
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
