"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session, init_db
from app.middleware.logging import RequestTimer, save_request_log
from app.models.schemas import ChatRequest, ChatResponse, ErrorResponse, HealthResponse
from app.services.gemini import get_gemini_service
from app.services.guardrails import GuardrailError, get_guardrails_service

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


app = FastAPI(
    title="LLM Gateway API",
    description="Enterprise-grade LLM gateway with input validation and request logging",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
)
async def health_check():
    """Check API health status."""
    return HealthResponse(status="healthy", version="1.0.0")


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["Chat"],
    summary="Send a message to Gemini",
    description="Send a message through the guardrails and receive a response from Gemini 2.5 Flash",
)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Process a chat request through guardrails and Gemini.

    - **message**: The user's input message (max 5000 characters)

    Returns the Gemini response along with token usage statistics.
    Blocked content and messages exceeding length limits will return 400 errors.
    """
    guardrails = get_guardrails_service()
    gemini = get_gemini_service()

    with RequestTimer() as timer:
        guardrails.validate(request.message)
        response_text, token_usage = await gemini.generate_response(request.message)

    background_tasks.add_task(
        save_request_log,
        session=session,
        input_prompt=request.message,
        output_response=response_text,
        latency_ms=timer.elapsed_ms,
        tokens_in=token_usage.get("input_tokens", 0),
        tokens_out=token_usage.get("output_tokens", 0),
        status="success",
    )

    logger.info(f"Chat request processed in {timer.elapsed_ms:.2f}ms")

    return ChatResponse(
        content=response_text,
        token_usage=token_usage,
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
